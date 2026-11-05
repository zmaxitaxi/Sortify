"""PyTorch model inference singleton service for Sortify."""

import io
import logging
import threading
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError
from torchvision import transforms

from backend.app.core.config import DEFAULT_MODEL_PATH, settings

logger = logging.getLogger(__name__)
Image.MAX_IMAGE_PIXELS = 25_000_000

# Canonical five-bin order for checkpoints without label metadata.
DEFAULT_CLASSES = ["compost", "glass", "landfill", "paper", "plastic"]


def detect_architecture(checkpoint: Any) -> str:
    """Select the network from checkpoint metadata or its state-dict keys."""
    if isinstance(checkpoint, dict):
        arch = checkpoint.get("architecture") or checkpoint.get("base_architecture")
        if arch is not None:
            arch = str(arch).strip().lower()
            if arch in {"mobilenet", "mobilenet_v2"}:
                return "mobilenet_v2"
            if arch == "resnet18":
                return arch
            raise ValueError(f"Unsupported checkpoint architecture: {arch}")
        state = checkpoint.get(
            "model_state_dict", checkpoint.get("state_dict", checkpoint)
        )
    else:
        state = checkpoint.state_dict()
    if "classifier.1.weight" in state:
        return "mobilenet_v2"
    if "fc.weight" in state:
        return "resnet18"
    raise ValueError("Checkpoint does not identify a supported architecture")


def build_model(arch: str, num_classes: int) -> torch.nn.Module:
    """Build a supported architecture without downloading pretrained weights."""
    from torchvision import models

    if arch == "mobilenet_v2":
        model = models.mobilenet_v2(weights=None)
        model.classifier[1] = torch.nn.Linear(model.last_channel, num_classes)
    elif arch == "resnet18":
        model = models.resnet18(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, num_classes)
    else:
        raise ValueError(f"Unsupported architecture: {arch}")
    return model


class ModelService:
    """Thread-safe singleton service for loading PyTorch weights and executing inference."""

    _instance: "ModelService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ModelService":  # noqa: PYI034
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance for test isolation."""
        with cls._lock:
            cls._instance = None

    def __init__(
        self,
        model_path: Path | str | None = None,
        class_names: list[str] | None = None,
        device: torch.device | str | None = None,
    ):
        with self._lock:
            if getattr(self, "_initialized", False):
                return

            self.model_path = Path(
                model_path if model_path is not None else settings.MODEL_PATH
            )
            if not self.model_path.is_absolute():
                self.model_path = Path(__file__).resolve().parents[3] / self.model_path

            if device is not None:
                self.device = torch.device(device)
            else:
                self.device = torch.device(
                    "cuda"
                    if torch.cuda.is_available()
                    else "mps"
                    if torch.backends.mps.is_available()
                    else "cpu"
                )

            # Cap CPU thread contention if running on CPU worker pool
            if self.device.type == "cpu":
                torch.set_num_threads(min(4, max(1, torch.get_num_threads())))

            self.model: torch.nn.Module | None = None
            self.class_names = (
                list(class_names) if class_names else list(DEFAULT_CLASSES)
            )

            # Preserve the current API model's preprocessing contract.
            self.transform = transforms.Compose(
                [
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                    ),
                ]
            )

            self._load_model()
            self._initialized = True

    def _load_model(self) -> None:
        """Loads weights into eval mode on target device if file exists, else sets fallback mode."""
        if not self.model_path.exists():
            logger.info(
                "%s not found. Running ModelService in fallback mode.",
                self.model_path,
            )
            self.model = None
            return

        try:
            checkpoint = torch.load(self.model_path, map_location=self.device)
            arch = detect_architecture(checkpoint)

            # 1. Unpack checkpoint metadata and state dict before building the network head
            if isinstance(checkpoint, dict):
                if "class_names" in checkpoint:
                    if not isinstance(checkpoint["class_names"], (list, tuple)):
                        raise ValueError("Checkpoint class_names must be a sequence")
                    self.class_names = list(checkpoint["class_names"])
                if "model_state_dict" in checkpoint:
                    state_dict = checkpoint["model_state_dict"]
                elif "state_dict" in checkpoint:
                    state_dict = checkpoint["state_dict"]
                else:
                    state_dict = {
                        k: v
                        for k, v in checkpoint.items()
                        if isinstance(v, torch.Tensor)
                    }
            elif hasattr(checkpoint, "state_dict"):
                state_dict = checkpoint.state_dict()
            else:
                state_dict = checkpoint

            head_key = "classifier.1.weight" if arch == "mobilenet_v2" else "fc.weight"
            num_classes = state_dict[head_key].shape[0]
            if (
                num_classes != len(self.class_names)
                or any(
                    not isinstance(name, str) or not name.strip()
                    for name in self.class_names
                )
                or len(set(self.class_names)) != num_classes
            ):
                raise ValueError("Checkpoint labels must match the classifier outputs")
            model = build_model(arch, num_classes)
            model.load_state_dict(state_dict)
            model.to(self.device)
            model.eval()
            self.model = model
            logger.info(
                "Loaded model weights from %s onto %s (classes: %d)",
                self.model_path,
                self.device,
                num_classes,
            )
        except (OSError, RuntimeError, KeyError, ValueError) as exc:
            logger.warning(
                "Failed to load weights from %s: %s. Running in fallback mode.",
                self.model_path,
                exc,
            )
            self.model = None

    def predict(self, image_bytes: bytes) -> dict[str, Any]:
        """Runs inference on uploaded image bytes.

        Returns:
            dict containing category, item_name, confidence, alternatives, and latency_ms.
        """
        start_time = time.perf_counter()

        # Validate and open image bytes, handling EXIF orientation and color formats
        try:
            with Image.open(io.BytesIO(image_bytes)) as raw_img:
                if raw_img.width <= 0 or raw_img.height <= 0:
                    raise ValueError(f"Invalid image dimensions: {raw_img.size}")
                if raw_img.width > 8192 or raw_img.height > 8192:
                    raise ValueError("Image dimensions exceed the 8192x8192 limit")
                try:
                    img = ImageOps.exif_transpose(raw_img)
                except (TypeError, ValueError, OSError):
                    img = raw_img
                img = img.convert("RGB")
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            DecompressionBombError,
        ) as err:
            logger.warning("[INFERENCE] Corrupted or invalid image payload: %s", err)
            raise

        if self.model is None:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "[INFERENCE] Fallback mock inference completed in %.2fms",
                elapsed_ms,
            )
            return {
                "category": "compost",
                "item_name": "Almond Milk Carton (Scaffold)",
                "confidence": 0.91,
                "alternatives": [
                    {"category": "paper", "confidence": 0.06},
                    {"category": "landfill", "confidence": 0.03},
                ],
                "is_mock": True,
                "latency_ms": elapsed_ms,
            }

        # Apply transformations and add batch dimension
        tensor = self.transform(img).unsqueeze(0).to(self.device)

        try:
            with torch.no_grad():
                outputs = self.model(tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]
                if probabilities.shape[0] != len(self.class_names):
                    raise RuntimeError("Model outputs do not match checkpoint labels")
                k = min(3, len(self.class_names))
                topk = torch.topk(probabilities, k)
                top_prob, top_idx = topk.values, topk.indices

                predicted_label = self.class_names[top_idx[0].item()]
                confidence = float(top_prob[0].item())

                alternatives = [
                    {
                        "category": self.class_names[top_idx[i].item()],
                        "confidence": round(float(top_prob[i].item()), 4),
                    }
                    for i in range(1, len(top_idx))
                ]
        except (RuntimeError, MemoryError) as exc:
            del tensor
            if self.device.type == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif self.device.type == "mps" and hasattr(torch, "mps"):
                torch.mps.empty_cache()
            logger.error("[INFERENCE] Forward pass failed on %s: %s", self.device, exc)
            raise RuntimeError(f"Inference execution failed: {exc}") from exc

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "[INFERENCE] Predicted %s (%.2f%%) in %.2fms",
            predicted_label,
            confidence * 100,
            elapsed_ms,
        )

        return {
            "category": predicted_label,
            "item_name": predicted_label.title(),
            "confidence": round(confidence, 4),
            "alternatives": alternatives,
            "is_mock": False,
            "latency_ms": elapsed_ms,
        }


# Global singleton instance
model_service = ModelService()

__all__ = [
    "DEFAULT_CLASSES",
    "DEFAULT_MODEL_PATH",
    "ModelService",
    "build_model",
    "detect_architecture",
    "model_service",
]

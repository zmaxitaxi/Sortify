"""Tests for classification pipeline hardening, error resilience, and benchmarking."""

import io
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image
from torchvision import models

from backend.app.main import app
from backend.app.services.model_service import ModelService
from backend.scripts.benchmark_inference import (
    calculate_percentile,
    run_inference_benchmark,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_custom_model_instances(monkeypatch):
    monkeypatch.setattr(ModelService, "_instance", None)


@pytest.mark.parametrize("city", ["berkeley", "san-francisco", "oakland"])
@pytest.mark.parametrize(
    "category", ["compost", "glass", "landfill", "paper", "plastic"]
)
def test_classify_preserves_municipal_rules(city, category, monkeypatch):
    from backend.app.services.municipal_rules import get_category_rule

    monkeypatch.setattr(
        ModelService,
        "predict",
        lambda self, image: {
            "category": category,
            "confidence": 0.9,
            "item_name": "Bottle",
        },
    )
    response = client.post(
        "/api/classify",
        params={"location": city},
        files={"file": ("photo.jpg", create_test_image(), "image/jpeg")},
    )
    assert response.status_code == 200
    assert (
        get_category_rule(category, city) in response.json()["disposal_tips"]["notes"]
    )


def create_test_image(
    size: tuple[int, int] = (100, 100),
    mode: str = "RGB",
    img_format: str = "JPEG",
) -> bytes:
    """Helper to create valid test image bytes."""
    color: Any = (
        "green" if mode == "RGB" else (0, 255, 0, 255) if mode == "RGBA" else 128
    )
    img = Image.new(mode, size, color=color)
    buffer = io.BytesIO()
    img.save(buffer, format=img_format)
    return buffer.getvalue()


def test_classify_standard_image():
    """Verify standard valid JPEG image passes through hardened classification pipeline."""
    payload = create_test_image((224, 224), "RGB", "JPEG")
    files = {"file": ("test.jpg", payload, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "item_name" in data
    assert "category" in data
    assert "confidence" in data
    assert "bin" in data
    assert "disposal_tips" in data
    assert isinstance(data["alternatives"], list)


@pytest.mark.parametrize(
    "size,desc",
    [
        ((1000, 20), "extreme_wide"),
        ((20, 1000), "extreme_tall"),
        ((5, 5), "micro_image"),
        ((1200, 1200), "high_resolution"),
    ],
)
def test_classify_extreme_aspect_ratios(size: tuple[int, int], desc: str):
    """Verify non-standard aspect ratios are processed without error."""
    payload = create_test_image(size, "RGB", "JPEG")
    files = {"file": (f"{desc}.jpg", payload, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["category"] in [
        "compost",
        "glass",
        "landfill",
        "paper",
        "plastic",
    ]


def test_classify_rgba_and_grayscale():
    """Verify RGBA 4-channel and Grayscale single-channel images are accepted and converted."""
    rgba_bytes = create_test_image((100, 100), "RGBA", "PNG")
    res_rgba = client.post(
        "/api/classify",
        files={"file": ("rgba.png", rgba_bytes, "image/png")},
    )
    assert res_rgba.status_code == 200

    gray_bytes = create_test_image((100, 100), "L", "JPEG")
    res_gray = client.post(
        "/api/classify",
        files={"file": ("gray.jpg", gray_bytes, "image/jpeg")},
    )
    assert res_gray.status_code == 200


def test_classify_corrupted_payload_returns_422():
    """Verify corrupted image payload with valid magic bytes returns HTTP 422 cleanly."""
    corrupted_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 30 + b"garbage_corrupted_stream"
    files = {"file": ("corrupted.jpg", corrupted_bytes, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 422
    assert "Could not read the image" in response.json()["detail"]


def test_classify_rejects_oversized_dimensions():
    payload = create_test_image((8193, 1), "RGB", "PNG")
    response = client.post(
        "/api/classify", files={"file": ("too-wide.png", payload, "image/png")}
    )
    assert response.status_code == 422


def test_classify_empty_payload():
    """Preserve the upload validator's HTTP 400 contract for empty files."""
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/api/classify", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_classify_timeout_protection(monkeypatch):
    """Verify inference taking longer than timeout raises HTTP 504 Gateway Timeout."""

    def slow_predict(self, image_bytes: bytes):
        import time

        time.sleep(0.3)
        return {"category": "compost", "confidence": 0.9}

    monkeypatch.setattr(ModelService, "predict", slow_predict)

    with patch("backend.app.routers.classify.settings") as mock_settings:
        mock_settings.INFERENCE_TIMEOUT_SECONDS = 0.05
        payload = create_test_image((50, 50))
        files = {"file": ("slow.jpg", payload, "image/jpeg")}
        response = client.post("/api/classify", files=files)

        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()


def test_classify_runtime_error_resilience(monkeypatch):
    """Verify PyTorch / CUDA RuntimeError returns HTTP 503 instead of crashing server."""

    def failing_predict(self, image_bytes: bytes):
        raise RuntimeError("CUDA device out of memory or kernel launch failure")

    monkeypatch.setattr(ModelService, "predict", failing_predict)

    payload = create_test_image((50, 50))
    files = {"file": ("error.jpg", payload, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_classify_unexpected_exception_resilience(monkeypatch):
    """Verify completely unexpected internal exception returns HTTP 500 without crashing."""

    def exploding_predict(self, image_bytes: bytes):
        raise ZeroDivisionError("Unexpected mathematical error in pipeline")

    monkeypatch.setattr(ModelService, "predict", exploding_predict)

    payload = create_test_image((50, 50))
    files = {"file": ("exploding.jpg", payload, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 500
    assert "unexpected error" in response.json()["detail"].lower()


def test_classify_deduplicates_alternatives(monkeypatch):
    """Verify alternatives filtering eliminates duplicate categories and primary category."""

    def mock_predict(self, image_bytes: bytes):
        return {
            "category": "plastic",
            "item_name": "Plastic Bottle",
            "confidence": 0.85,
            "alternatives": [
                {"category": "plastic", "confidence": 0.85},
                {"category": "metal", "confidence": 0.10},  # maps to plastic
                {"category": "glass", "confidence": 0.04},
                {"category": "glass", "confidence": 0.03},  # duplicate of alt
            ],
        }

    monkeypatch.setattr(ModelService, "predict", mock_predict)

    payload = create_test_image((50, 50))
    files = {"file": ("test.jpg", payload, "image/jpeg")}
    response = client.post("/api/classify", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "plastic"

    alt_categories = [alt["category"] for alt in data["alternatives"]]
    assert alt_categories == ["glass"]


def test_classify_null_alternatives_metadata(monkeypatch):
    """Verify model prediction with null or omitted alternatives validates cleanly."""

    def mock_predict(self, image_bytes: bytes):
        return {
            "category": "paper",
            "confidence": 0.88,
            "alternatives": None,
        }

    monkeypatch.setattr(ModelService, "predict", mock_predict)
    payload = create_test_image((50, 50))
    res = client.post(
        "/api/classify", files={"file": ("test.jpg", payload, "image/jpeg")}
    )
    assert res.status_code == 200
    assert res.json()["alternatives"] == []
    assert res.json()["category"] == "paper"


def test_classify_unknown_model_label_fallback(monkeypatch):
    """Verify unrecognized model labels safely fall back to landfill category."""

    def mock_predict(self, image_bytes: bytes):
        return {
            "category": "unrecognized_electronic_gadget",
            "confidence": 0.55,
        }

    monkeypatch.setattr(ModelService, "predict", mock_predict)
    payload = create_test_image((50, 50))
    res = client.post(
        "/api/classify", files={"file": ("test.jpg", payload, "image/jpeg")}
    )
    assert res.status_code == 200
    assert res.json()["category"] == "landfill"
    assert res.json()["bin_color"] == "Gray"


@pytest.mark.parametrize("configured", [False, True])
def test_model_service_dynamic_checkpoint_dimension(tmp_path, monkeypatch, configured):
    """Verify ModelService adapts classification head to checkpoint class count."""
    mobilenet = models.mobilenet_v2(weights=None)
    mobilenet.classifier[1] = torch.nn.Linear(mobilenet.last_channel, 6)
    ckpt_path = tmp_path / "custom_mobilenet.pth"
    torch.save(
        {
            "model_state_dict": mobilenet.state_dict(),
            "class_names": ["glass", "paper", "cardboard", "plastic", "metal", "trash"],
        },
        ckpt_path,
    )

    if configured:
        from backend.app.services import inference as service_module

        monkeypatch.setattr(
            service_module,
            "settings",
            service_module.settings.model_copy(update={"MODEL_PATH": str(ckpt_path)}),
        )
        svc = ModelService()
    else:
        svc = ModelService(model_path=ckpt_path)
    assert svc.model is not None
    assert len(svc.class_names) == 6
    assert svc.model.classifier[1].out_features == 6
    assert svc.predict(create_test_image())["is_mock"] is False


def test_default_settings_use_existing_checkpoint_location(monkeypatch):
    from backend.app.core.config import Settings
    from backend.app.services.model_service import DEFAULT_MODEL_PATH

    monkeypatch.delenv("MODEL_PATH", raising=False)
    cfg = Settings(_env_file=None)
    assert Path(cfg.MODEL_PATH) == DEFAULT_MODEL_PATH
    assert DEFAULT_MODEL_PATH.parts[-4:] == (
        "backend",
        "app",
        "models",
        "sortify_mvp_v1.pth",
    )


def test_relative_checkpoint_path_does_not_depend_on_cwd(tmp_path, monkeypatch):
    from backend.app.services import model_service as service_module

    monkeypatch.chdir(tmp_path)
    service = ModelService(model_path="ml/models/custom.pth")
    root = Path(service_module.__file__).resolve().parents[3]
    assert service.model_path == root / "ml/models/custom.pth"


@pytest.mark.parametrize("loaded", [False, True])
def test_corrupt_jpeg_header_returns_422_even_with_model(monkeypatch, loaded):
    monkeypatch.setattr(
        "backend.app.services.model_service.model_service.model",
        torch.nn.Identity() if loaded else None,
    )
    response = client.post(
        "/api/classify", files={"file": ("broken.jpg", b"\xff\xd8\xff", "image/jpeg")}
    )
    assert response.status_code == 422


def test_checkpoint_with_missing_labels_cannot_load_six_outputs(tmp_path):
    mobilenet = models.mobilenet_v2(weights=None)
    mobilenet.classifier[1] = torch.nn.Linear(mobilenet.last_channel, 6)
    checkpoint = tmp_path / "unlabeled.pth"
    torch.save(mobilenet.state_dict(), checkpoint)
    assert ModelService(model_path=checkpoint).model is None


def test_calculate_percentile():
    """Verify percentile calculation with boundary clamping."""
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_percentile(data, 0.0) == 10.0
    assert calculate_percentile(data, 50.0) == 30.0
    assert calculate_percentile(data, 100.0) == 50.0
    # Clamping out-of-range percentiles
    assert calculate_percentile(data, -10.0) == 10.0
    assert calculate_percentile(data, 150.0) == 50.0
    assert calculate_percentile([], 50.0) == 0.0


def test_benchmark_inference_script():
    """Verify benchmark inference helper executes across 20 synthetic images."""
    report = run_inference_benchmark(warmup_runs=1, force_cpu=True)
    assert report["count"] == 20
    assert report["mean_ms"] >= 0.0
    assert report["median_ms"] >= 0.0
    assert len(report["individual_results"]) == 20

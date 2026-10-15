"""Package the fine-tuned Sortify ResNet-18 for backend integration.

Writes resnet18_sortify.pth (state_dict), classes.json and metadata.json to
ml/models/mvp_package/.

Run from the repository root:
    python ml/scripts/export_model.py
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import torch
from torch import nn
from torchvision import models

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINT = REPO_ROOT / "ml" / "models" / "resnet18_finetuned.pth"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ml" / "models" / "mvp_package"
DEFAULT_FILENAME = "resnet18_sortify.pth"

EXPECTED_CLASSES = {"paper", "plastic", "glass", "compost", "landfill"}
INPUT_RESOLUTION = [224, 224]
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_model(num_classes: int) -> nn.Module:
    """Bare ResNet-18 with the 5-bin head, no pretrained download needed."""
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {path}. Run ml/scripts/fine_tune.py first."
        )
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    for key in ("model_state_dict", "class_names"):
        if key not in checkpoint:
            raise KeyError(f"Checkpoint is missing '{key}'.")
    return checkpoint


def package_checkpoint(
    model: nn.Module,
    classes: list[str],
    output_dir: Path,
    filename: str = DEFAULT_FILENAME,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save classes.json as an index -> name mapping
    class_map = {str(i): name for i, name in enumerate(classes)}
    with open(output_dir / "classes.json", "w") as f:
        json.dump(class_map, f, indent=2)

    # Save state dict (CPU tensors only, so it loads on any machine)
    state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
    torch.save(state_dict, output_dir / filename)
    print(f"Saved weights and classes.json to {output_dir}")


def write_metadata(
    checkpoint: dict,
    checkpoint_path: Path,
    classes: list[str],
    output_dir: Path,
    filename: str = DEFAULT_FILENAME,
) -> None:
    # fine_tune.py does not store a date, so use when the checkpoint was written.
    trained_at = datetime.fromtimestamp(checkpoint_path.stat().st_mtime, tz=UTC)

    metadata = {
        "base_architecture": "resnet18",
        "pretrained_weights": "ImageNet (torchvision ResNet18_Weights.DEFAULT)",
        "fine_tuned_layers": ["layer3", "layer4", "fc"],
        "num_classes": len(classes),
        "class_names": classes,
        "weights_file": filename,
        "training_date": trained_at.date().isoformat(),
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "final_validation_accuracy": checkpoint.get("val_accuracy"),
        "best_epoch": checkpoint.get("best_epoch"),
        "test_accuracy": checkpoint.get("test_accuracy"),
        "input_resolution": INPUT_RESOLUTION,
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "source_checkpoint": checkpoint_path.name,
    }

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata.json to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package the Sortify ResNet-18 for backend integration."
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--filename", default=DEFAULT_FILENAME)
    args = parser.parse_args()

    checkpoint = load_checkpoint(args.checkpoint)
    classes = list(checkpoint["class_names"])

    if set(classes) != EXPECTED_CLASSES or len(classes) != len(EXPECTED_CLASSES):
        raise ValueError(
            f"Unexpected classes {classes}; expected {sorted(EXPECTED_CLASSES)}."
        )

    # Loading into a fresh model confirms the keys and shapes match ResNet-18.
    model = build_model(len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print(f"Trained class order: {classes}")
    package_checkpoint(model, classes, args.output_dir, args.filename)
    write_metadata(checkpoint, args.checkpoint, classes, args.output_dir, args.filename)


if __name__ == "__main__":
    main()

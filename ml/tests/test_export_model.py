"""Verify the exported model package loads with only state_dict + classes.json.

The pytest test imports build_model and package_checkpoint from
ml/scripts/export_model.py to generate a package in tmp_path, then loads it
using only the state_dict and classes.json, like the backend team's loader.
The CLI check in main() reads an existing package and does not read the
training checkpoint.

Run from the repository root:
    pytest ml/tests/test_export_model.py
    python ml/tests/test_export_model.py
    python ml/tests/test_export_model.py --package-dir ml/models/mvp_package
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch import nn
from torchvision import models

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "ml" / "scripts"))

from export_model import build_model, package_checkpoint

DEFAULT_PACKAGE = REPO_ROOT / "ml" / "models" / "mvp_package"
WEIGHTS_FILE = "resnet18_sortify.pth"


def test_export_and_load_package(tmp_path: Path):
    model = build_model(5)
    classes = ["compost", "glass", "landfill", "paper", "plastic"]

    # Export into tmp_path
    package_checkpoint(model, classes, tmp_path, "test_model.pth")

    # 1. Verify classes.json
    with open(tmp_path / "classes.json") as f:
        class_map = json.load(f)
    assert len(class_map) == 5
    assert class_map["0"] == "compost"

    # 2. Verify state_dict loading
    state_dict = torch.load(tmp_path / "test_model.pth", weights_only=True)
    fresh_model = build_model(5)
    fresh_model.load_state_dict(state_dict)
    fresh_model.eval()

    # 3. Verify forward pass
    with torch.no_grad():
        probs = torch.softmax(fresh_model(torch.randn(1, 3, 224, 224)), dim=1)[0]
    assert probs.shape == (5,)
    assert torch.isfinite(probs).all()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the exported Sortify model package."
    )
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    args = parser.parse_args()

    # 1. classes.json
    with open(args.package_dir / "classes.json") as f:
        class_map = json.load(f)
    expected_keys = [str(i) for i in range(len(class_map))]
    assert sorted(class_map) == sorted(expected_keys), f"Bad keys: {list(class_map)}"
    classes = [class_map[k] for k in expected_keys]
    assert len(classes) == 5, f"Expected 5 classes, got {len(classes)}"
    print(f"classes.json OK: {class_map}")

    # 2. state_dict only (weights_only=True rejects anything but tensors/primitives)
    state_dict = torch.load(
        args.package_dir / WEIGHTS_FILE, map_location="cpu", weights_only=True
    )
    assert "model_state_dict" not in state_dict, "Expected a bare state_dict."

    # 3. Rebuild the architecture and load
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(state_dict)
    model.eval()
    print("state_dict loaded into resnet18 (strict)")

    # 4. Forward pass on a dummy 224x224 input
    with torch.no_grad():
        probs = torch.softmax(model(torch.randn(1, 3, 224, 224)), dim=1)[0]
    assert probs.shape == (len(classes),)
    assert torch.isfinite(probs).all()
    assert abs(probs.sum().item() - 1.0) < 1e-4

    print("Dummy forward pass OK:")
    for name, p in zip(classes, probs.tolist()):
        print(f"  {name:<9} {p:.1%}")
    print("PASS")


if __name__ == "__main__":
    main()

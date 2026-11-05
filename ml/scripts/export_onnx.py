"""Export a trained FP32 checkpoint, publishing only after ONNX parity passes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.scripts.dataset import IMAGENET_MEAN, IMAGENET_STD, get_eval_transforms
from ml.scripts.evaluate import (
    DEFAULT_CLASSES,
    build_model,
    detect_architecture,
    load_classes_from_package,
)

DEFAULT_OUTPUT = REPO_ROOT / "ml/models/sortify_v2.onnx"
TOLERANCE = 1e-4


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def resolve_checkpoint(requested: Path | None) -> Path:
    candidates = (
        [requested]
        if requested is not None
        else [
            REPO_ROOT / "ml/models" / name
            for name in ("sortify_v2.pth", "sortify_mvp_v1.pth", "mobilenet_v2.pth")
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "No trained checkpoint found. Pass --checkpoint or train the model first. "
        "Initialized weights are never exported as a fallback."
    )


def load_model(path: Path) -> tuple[torch.nn.Module, str]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise TypeError("Checkpoint must be a state dictionary or training bundle")
    classes = checkpoint.get("class_names") or load_classes_from_package(path)
    if classes != DEFAULT_CLASSES:
        raise ValueError(f"Checkpoint must declare class_names={DEFAULT_CLASSES}")
    state = checkpoint.get("model_state_dict", checkpoint)
    if not isinstance(state, dict) or not state:
        raise ValueError("Checkpoint must contain a nonempty model_state_dict")
    architecture = detect_architecture(checkpoint)
    model = build_model(architecture)
    model.load_state_dict(state, strict=True)
    return model.cpu().eval(), architecture


def image_samples(directory: Path, count: int) -> tuple[torch.Tensor, list[dict]]:
    """Take deterministic, evenly spaced real files, using evaluation preprocessing."""
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    if not files:
        raise ValueError(f"No real images found in {directory}")
    indices = np.linspace(0, len(files) - 1, min(count, len(files)), dtype=int)
    transform = get_eval_transforms()
    tensors, evidence = [], []
    for index in indices:
        path = files[index]
        with Image.open(path) as image:
            tensors.append(transform(image.convert("RGB")))
        evidence.append(
            {"file": path.relative_to(directory).as_posix(), "sha256": sha256(path)}
        )
    return torch.stack(tensors), evidence


def verify_parity(model, session, inputs: torch.Tensor, name: str) -> dict:
    with torch.inference_mode():
        expected = model(inputs).numpy()
    actual = session.run(["output"], {"input": inputs.numpy()})[0]
    if (
        expected.shape != (len(inputs), len(DEFAULT_CLASSES))
        or actual.shape != expected.shape
    ):
        raise ValueError(
            f"{name}: unexpected output shapes {expected.shape} / {actual.shape}"
        )
    if not np.isfinite(expected).all() or not np.isfinite(actual).all():
        raise ValueError(f"{name}: nonfinite logits")
    difference = float(np.max(np.abs(expected - actual)))
    if difference >= TOLERANCE:
        raise ValueError(
            f"{name}: maximum absolute difference {difference:.8g} >= {TOLERANCE}"
        )
    return {"name": name, "batch_size": len(inputs), "max_abs_diff": difference}


def export_and_verify(
    checkpoint_path: Path,
    output_path: Path,
    image_dir: Path,
    report_path: Path | None = None,
    num_images: int = 10,
) -> dict:
    if num_images < 1:
        raise ValueError("num_images must be positive")
    checkpoint_path = resolve_checkpoint(checkpoint_path)
    output_path = output_path.resolve()
    report_path = (report_path or output_path.with_suffix(".json")).resolve()
    if len({checkpoint_path, output_path, report_path}) != 3:
        raise ValueError("Checkpoint, ONNX output, and report paths must be distinct")
    model, architecture = load_model(checkpoint_path)
    images, evidence = image_samples(image_dir.resolve(), num_images)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generator = torch.Generator().manual_seed(42)
    example = torch.randn(2, 3, 224, 224, generator=generator)

    # A failed checker/parity run leaves any previously verified artifact intact.
    with tempfile.TemporaryDirectory(
        dir=output_path.parent, prefix=".onnx-export-"
    ) as directory:
        temporary = Path(directory) / output_path.name
        torch.onnx.export(
            model,
            (example,),
            str(temporary),
            input_names=["input"],
            output_names=["output"],
            opset_version=18,
            dynamo=True,
            dynamic_shapes=({0: torch.export.Dim("batch_size", min=1)},),
            external_data=False,
        )
        graph = onnx.load(str(temporary))
        for value in [*graph.graph.input, *graph.graph.output]:
            if value.type.tensor_type.shape.dim[0].dim_param != "batch_size":
                raise ValueError(
                    "Export must preserve a dynamic batch_size input and output"
                )
        preprocessing = {
            "resize_short_edge": 256,
            "center_crop": [224, 224],
            "color": "RGB",
            "scale": "divide by 255",
            "mean": IMAGENET_MEAN,
            "std": IMAGENET_STD,
            "layout": "NCHW float32",
        }
        onnx.helper.set_model_props(
            graph,
            {
                "class_names": json.dumps(DEFAULT_CLASSES),
                "architecture": architecture,
                "source_checkpoint": checkpoint_path.name,
                "source_checkpoint_sha256": sha256(checkpoint_path),
                "preprocessing": json.dumps(preprocessing),
                "output": "Unnormalized logits in class_names order; apply softmax for probabilities.",
            },
        )
        onnx.save(graph, str(temporary))
        onnx.checker.check_model(str(temporary), full_check=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        session = ort.InferenceSession(
            str(temporary), sess_options=options, providers=["CPUExecutionProvider"]
        )
        cases = [
            verify_parity(
                model,
                session,
                torch.randn(size, 3, 224, 224, generator=generator),
                f"synthetic_{size}",
            )
            for size in (1, 2, 4)
        ]
        cases.append(verify_parity(model, session, images, "real_images"))
        report = {
            "passed": True,
            "architecture": architecture,
            "source_checkpoint": checkpoint_path.name,
            "source_checkpoint_sha256": sha256(checkpoint_path),
            "class_names": DEFAULT_CLASSES,
            "preprocessing": preprocessing,
            "opset": 18,
            "provider": "CPUExecutionProvider",
            "versions": {
                "torch": torch.__version__,
                "onnx": onnx.__version__,
                "onnxruntime": ort.__version__,
            },
            "onnx_file": output_path.name,
            "onnx_bytes": temporary.stat().st_size,
            "onnx_sha256": sha256(temporary),
            "tolerance": TOLERANCE,
            "max_abs_diff": max(case["max_abs_diff"] for case in cases),
            "cases": cases,
            "real_images": evidence,
        }
        # Stage the report in its own destination filesystem before publishing.
        with tempfile.TemporaryDirectory(
            dir=report_path.parent, prefix=".onnx-report-"
        ) as report_dir:
            temporary_report = Path(report_dir) / report_path.name
            temporary_report.write_text(json.dumps(report, indent=2) + "\n")
            temporary.replace(output_path)
            temporary_report.replace(report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--image-dir", type=Path, default=REPO_ROOT / "data/processed/val"
    )
    parser.add_argument("--num-images", type=int, default=10)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    report = export_and_verify(
        resolve_checkpoint(args.checkpoint),
        args.output,
        args.image_dir,
        args.report,
        args.num_images,
    )
    print(
        f"Parity PASSED: max |PyTorch - ONNX| = {report['max_abs_diff']:.8g} < {TOLERANCE}"
    )
    print(
        f"Verified model: {args.output}; source checkpoint: {report['source_checkpoint']}"
    )


if __name__ == "__main__":
    main()

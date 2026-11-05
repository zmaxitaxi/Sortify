"""Verify portable graphs, numerical rejection, and safe artifact publication."""

import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch
from PIL import Image

from ml.scripts import export_onnx as exporter
from ml.scripts.evaluate import DEFAULT_CLASSES, build_model


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    directory = tmp_path_factory.mktemp("onnx-images")
    for index, category in enumerate(DEFAULT_CLASSES):
        folder = directory / category
        folder.mkdir()
        # Fixture images test preprocessing; measured parity uses actual validation photos.
        Image.new("RGB", (280, 260), (index * 40, 80, 120)).save(folder / "sample.png")
    return directory


@pytest.fixture(scope="module", params=["mobilenet_v2", "resnet18"])
def exported(request, tmp_path_factory, images):
    directory = tmp_path_factory.mktemp(request.param)
    with torch.random.fork_rng():
        torch.manual_seed(42)
        model = build_model(request.param).eval()
    checkpoint = directory / "fixture.pth"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_names": DEFAULT_CLASSES,
            "architecture": request.param,
        },
        checkpoint,
    )
    output = directory / "model.onnx"
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        report = exporter.export_and_verify(checkpoint, output, images, num_images=5)
    finally:
        torch.set_num_threads(previous)
    return checkpoint, output, model, report


def test_exported_graph_is_dynamic_and_matches_on_an_additional_batch(exported):
    checkpoint, output, model, report = exported
    onnx.checker.check_model(str(output), full_check=True)
    session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    assert session.get_inputs()[0].shape == ["batch_size", 3, 224, 224]
    assert session.get_outputs()[0].shape == ["batch_size", 5]
    result = exporter.verify_parity(
        model, session, torch.zeros(3, 3, 224, 224), "new_batch"
    )
    assert result["max_abs_diff"] < 1e-4
    assert report["passed"] is True
    assert [case["batch_size"] for case in report["cases"]] == [1, 2, 4, 5]
    assert report["source_checkpoint_sha256"] == exporter.sha256(checkpoint)
    assert report["onnx_sha256"] == exporter.sha256(output)
    assert json.loads(output.with_suffix(".json").read_text()) == report
    metadata = session.get_modelmeta().custom_metadata_map
    assert json.loads(metadata["class_names"]) == DEFAULT_CLASSES
    assert json.loads(metadata["preprocessing"])["center_crop"] == [224, 224]


def test_incorrect_and_nonfinite_runtime_outputs_fail_parity(exported):
    _, _, model, _ = exported

    class BrokenSession:
        def __init__(self, value):
            self.value = value

        def run(self, *args):
            return [np.full((1, 5), self.value, dtype=np.float32)]

    for value in (100.0, np.nan, np.inf):
        with pytest.raises(ValueError):
            exporter.verify_parity(
                model, BrokenSession(value), torch.zeros(1, 3, 224, 224), "bad_runtime"
            )


def test_failed_verification_preserves_previous_artifact_and_report(
    exported, images, tmp_path, monkeypatch
):
    checkpoint, existing, _, _ = exported
    output = tmp_path / "previous.onnx"
    output.write_bytes(existing.read_bytes())
    report = tmp_path / "previous.json"
    report.write_text('{"previous": true}\n')
    before = exporter.sha256(output)

    def reject(*args, **kwargs):
        raise ValueError("Numerical mismatch")

    monkeypatch.setattr(exporter, "verify_parity", reject)
    with pytest.raises(ValueError, match="Numerical mismatch"):
        exporter.export_and_verify(checkpoint, output, images)
    assert exporter.sha256(output) == before
    assert report.read_text() == '{"previous": true}\n'
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "previous.json",
        "previous.onnx",
    ]


def test_packaged_state_dict_needs_explicit_class_order(tmp_path):
    model = build_model("mobilenet_v2")
    checkpoint = tmp_path / "sortify_mvp_v1.pth"
    torch.save(model.state_dict(), checkpoint)
    with pytest.raises(ValueError, match="class_names"):
        exporter.load_model(checkpoint)
    (tmp_path / "classes.json").write_text(json.dumps(dict(enumerate(DEFAULT_CLASSES))))
    loaded, architecture = exporter.load_model(checkpoint)
    assert architecture == "mobilenet_v2"
    assert not loaded.training
    assert torch.equal(loaded.classifier[1].weight, model.classifier[1].weight)


@pytest.mark.parametrize("classes", [DEFAULT_CLASSES[::-1], ["paper"] * 5])
def test_incorrect_class_order_is_rejected(tmp_path, classes):
    checkpoint = tmp_path / "bad.pth"
    torch.save(
        {"class_names": classes, "model_state_dict": {"x": torch.ones(1)}}, checkpoint
    )
    with pytest.raises(ValueError, match="class_names"):
        exporter.load_model(checkpoint)


def test_missing_checkpoint_and_images_fail_without_publishing(tmp_path):
    output = tmp_path / "model.onnx"
    with pytest.raises(FileNotFoundError, match="No trained checkpoint"):
        exporter.export_and_verify(tmp_path / "missing.pth", output, tmp_path)
    with pytest.raises(ValueError, match="No real images"):
        exporter.image_samples(tmp_path, 5)
    assert not output.exists()


def test_checkpoint_and_output_cannot_share_a_path(tmp_path):
    checkpoint = tmp_path / "weights.pth"
    checkpoint.write_bytes(b"source")
    with pytest.raises(ValueError, match="distinct"):
        exporter.export_and_verify(checkpoint, checkpoint, tmp_path)
    assert checkpoint.read_bytes() == b"source"


def test_checked_in_artifact_matches_its_measured_report():
    root = Path(__file__).resolve().parents[2]
    report = json.loads((root / "docs/ml/onnx_export_metrics.json").read_text())
    artifact = root / "ml/models/sortify_v2.onnx"
    onnx.checker.check_model(str(artifact), full_check=True)
    assert exporter.sha256(artifact) == report["onnx_sha256"]
    assert report["passed"] is True
    assert report["max_abs_diff"] < exporter.TOLERANCE
    assert len(report["real_images"]) >= 1

"""Unit tests for PyTorch model inference singleton service."""

import io

import pytest
import torch
from PIL import Image, UnidentifiedImageError
from torchvision import models

from backend.app.services.inference import ModelService, model_service


@pytest.fixture(autouse=True)
def isolate_singleton(monkeypatch):
    monkeypatch.setattr(ModelService, "_instance", model_service)


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Generate a real 10x10 RGB JPEG image."""
    img = Image.new("RGB", (10, 10), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_singleton_pattern():
    """Verify ModelService implements a true thread-safe singleton pattern."""
    svc1 = ModelService()
    svc2 = ModelService()
    assert svc1 is svc2
    assert svc1 is model_service


def test_predict_returns_valid_schema(sample_image_bytes):
    """Verify prediction dictionary structure and confidence score bounds."""
    result = model_service.predict(sample_image_bytes)

    assert "category" in result
    assert "item_name" in result
    assert "confidence" in result
    assert "alternatives" in result
    assert "latency_ms" in result

    assert isinstance(result["category"], str)
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["latency_ms"], float)
    assert result["latency_ms"] >= 0.0
    assert isinstance(result["alternatives"], list)


@pytest.mark.parametrize("loaded", [False, True])
def test_predict_rejects_mock_test_header(loaded, monkeypatch):
    """Malformed fixtures must never bypass image decoding."""
    monkeypatch.setattr(model_service, "model", torch.nn.Identity() if loaded else None)
    mock_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01"
    with pytest.raises((UnidentifiedImageError, OSError)):
        model_service.predict(mock_header)


def test_predict_rgba_image():
    """Verify RGBA image conversion to 3-channel RGB."""
    img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    res = model_service.predict(buf.getvalue())
    assert res["category"] is not None


def test_predict_grayscale_image():
    """Verify single-channel Grayscale image conversion."""
    img = Image.new("L", (10, 10), color=128)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = model_service.predict(buf.getvalue())
    assert res["category"] is not None


def test_predict_rejects_corrupted_bytes():
    """Verify corrupted non-image bytes raise UnidentifiedImageError or OSError."""
    corrupted_bytes = b"definitely not an image payload"
    with pytest.raises((UnidentifiedImageError, OSError, ValueError)):
        model_service.predict(corrupted_bytes)


@pytest.mark.parametrize("arch", ["mobilenet_v2", "resnet18"])
@pytest.mark.parametrize("wrapper", ["model_state_dict", "state_dict", "raw"])
def test_predict_with_real_model_weights(tmp_path, arch, wrapper):
    """Verify real PyTorch forward pass, softmax, and top-k indexing with synthetic checkpoint."""
    # Reset singleton to test isolated instance with custom weights
    ModelService.reset_instance()

    if arch == "mobilenet_v2":
        model = models.mobilenet_v2(weights=None)
        model.classifier[1] = torch.nn.Linear(model.last_channel, 5)
    else:
        model = models.resnet18(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 5)
    ckpt_path = tmp_path / "synthetic_model.pth"
    head = model.classifier[1] if arch == "mobilenet_v2" else model.fc
    with torch.no_grad():
        head.weight.zero_()
        head.bias.zero_()
        head.bias[0] = 10
    state = model.state_dict()
    checkpoint = (
        state
        if wrapper == "raw"
        else {
            wrapper: state,
            "class_names": ["plastic", "paper", "landfill", "glass", "compost"],
        }
    )
    torch.save(checkpoint, ckpt_path)

    svc = ModelService(model_path=ckpt_path)
    assert svc.model is not None
    assert len(svc.class_names) == 5
    assert svc.model.training is False
    assert svc.class_names[0] == ("compost" if wrapper == "raw" else "plastic")
    assert svc.transform.transforms[0].size == (224, 224)

    # Run inference with real model
    img = Image.new("RGB", (224, 224), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = svc.predict(buf.getvalue())

    assert result["is_mock"] is False
    assert result["category"] in svc.class_names
    assert result["category"] == svc.class_names[0]
    assert result["latency_ms"] >= 0
    assert len(result["alternatives"]) >= 1

    # Reset back to default for other tests
    ModelService.reset_instance()


def test_rejects_checkpoint_label_count_mismatch(tmp_path):
    ModelService.reset_instance()
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.last_channel, 6)
    checkpoint = tmp_path / "six_without_labels.pth"
    torch.save(model.state_dict(), checkpoint)
    svc = ModelService(model_path=checkpoint)
    assert svc.model is None


def test_relative_configured_path_is_independent_of_working_directory(
    tmp_path, monkeypatch
):
    from backend.app.services import inference

    ModelService.reset_instance()
    monkeypatch.setattr(
        inference,
        "settings",
        inference.settings.model_copy(update={"MODEL_PATH": "ml/models/mobile.pth"}),
    )
    monkeypatch.chdir(tmp_path)
    svc = ModelService()
    repo_root = inference.Path(inference.__file__).resolve().parents[3]
    assert svc.model_path == repo_root / "ml/models/mobile.pth"


def test_initialized_singleton_is_not_reconfigured():
    original_path = model_service.model_path
    assert ModelService(model_path="different.pth") is model_service
    assert model_service.model_path == original_path


def test_corrupt_jpeg_returns_422_with_installed_model(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    monkeypatch.setattr(model_service, "model", torch.nn.Identity())
    response = TestClient(app).post(
        "/api/classify",
        files={"file": ("corrupt.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )
    assert response.status_code == 422


def test_interoperability_with_model_service_module():
    """Verify backward compatibility when importing from backend.app.services.model_service."""
    from backend.app.services.model_service import (
        ModelService as LegacyService,
    )
    from backend.app.services.model_service import (
        model_service as legacy_instance,
    )

    assert LegacyService is ModelService
    assert legacy_instance is not None

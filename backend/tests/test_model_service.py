"""Unit tests for ModelService singleton and inference fallback."""

import io

import pytest
from PIL import Image, UnidentifiedImageError

from backend.app.services.model_service import ModelService, model_service


def _create_sample_jpeg() -> bytes:
    """Generate a valid 1x1 JPEG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), color="red")
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_model_service_predict_valid_image():
    """Verify ModelService.predict successfully runs on a valid image."""
    image_bytes = _create_sample_jpeg()
    result = model_service.predict(image_bytes)

    assert "category" in result
    assert "confidence" in result
    assert "alternatives" in result
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert len(result["alternatives"]) > 0


def test_model_service_predict_corrupted_image():
    """Verify ModelService.predict raises an exception on corrupted payload."""
    corrupted_bytes = b"\xff\xd8\xff\x00\x00\x00invalid_payload_not_image"
    service = ModelService()

    with pytest.raises((UnidentifiedImageError, OSError)):
        service.predict(corrupted_bytes)


def test_model_service_fallback():
    # Pass a path that definitely doesn't exist
    service = ModelService(model_path="non_existent_model.pth")
    # Verify fallback mode
    assert service.model is None

    result = service.predict(_create_sample_jpeg())

    assert "category" in result
    assert result["is_mock"] is True

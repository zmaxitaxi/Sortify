"""Week 1 image upload route."""

from fastapi import APIRouter, File, UploadFile

from backend.app.services.uploads import store_image_upload

router = APIRouter()


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):  # noqa: B008
    """Save an uploaded image locally and return a receipt."""
    return await store_image_upload(file)

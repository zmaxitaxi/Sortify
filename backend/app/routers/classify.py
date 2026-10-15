"""Classification API router."""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from backend.app.core.config import settings
from backend.app.schemas import (
    ClassificationAlternative,
    ClassifyResponse,
    DisposalTip,
)
from backend.app.services.tips_service import get_disposal_guidance

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


@router.post("/classify", response_model=ClassifyResponse)
def classify_item(
    file: UploadFile = File(...),  # noqa: B008
    location: str = Query("berkeley", description="Municipality name"),
):
    """Ingest image upload and return waste classification result."""
    # 1. Enforce media type validation (HTTP 415)
    if not file.content_type or not (
        file.content_type.startswith("image/")
        or file.content_type in ALLOWED_IMAGE_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Image required (JPEG, PNG, WEBP, GIF).",
        )

    # 2. Enforce file size limit (HTTP 413)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Payload too large. File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
        )

    file.file.seek(0, 2)
    actual_size = file.file.tell()
    file.file.seek(0)
    if actual_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Payload too large. File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
        )

    # Category is still the Week 3 mock. Disposal copy comes from the tips engine.
    item_name = "Almond Milk Carton (Scaffold)"
    category = "compost"
    confidence = 0.91
    guidance = get_disposal_guidance(category, item_name, location)

    return ClassifyResponse(
        item_name=item_name,
        category=category,
        confidence=confidence,
        location=location.lower(),
        disposal_tip=guidance["tip"],
        bin_color="Green",
        bin="Green Compost Bin",
        disposal_tips=DisposalTip(
            action=guidance["action"],
            bin_type=guidance["bin_type"],
            notes=guidance["notes"],
        ),
        alternatives=[
            ClassificationAlternative(category="paper", confidence=0.06),
            ClassificationAlternative(category="landfill", confidence=0.03),
        ],
    )

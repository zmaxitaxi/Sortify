"""Classification API router with timeout protection and hardened error resilience."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from PIL import UnidentifiedImageError
from PIL.Image import DecompressionBombError

from backend.app.core.config import settings
from backend.app.schemas import (
    ClassificationAlternative,
    ClassifyResponse,
    DisposalTip,
)
from backend.app.schemas.schemas import ALLOWED_CATEGORIES, BIN_COLORS
from backend.app.services.inference_runner import InferenceBusyError, inference_runner
from backend.app.services.model_service import ModelService, model_service
from backend.app.services.municipal_rules import get_category_rule
from backend.app.services.tips_service import get_disposal_guidance, get_disposal_tip
from backend.app.utils.validators import validate_image_upload

logger = logging.getLogger(__name__)

router = APIRouter()

IMAGE_DECODE_ERRORS = (
    UnidentifiedImageError,
    OSError,
    ValueError,
    SyntaxError,
    DecompressionBombError,
)

# Translates raw model prediction labels to canonical app categories.
LABEL_TO_CATEGORY = {
    "compost": "compost",
    "glass": "glass",
    "landfill": "landfill",
    "paper": "paper",
    "plastic": "plastic",
    # Legacy compatibility aliases
    "trash": "landfill",
    "cardboard": "paper",
    "metal": "plastic",
    "organic": "compost",
}


def get_model_service() -> ModelService:
    """Dependency provider returning the singleton ModelService."""
    return model_service


@router.post("/classify", response_model=ClassifyResponse)
async def classify_item(
    location: str = Query("berkeley", description="Municipality name"),
    file: UploadFile = Depends(validate_image_upload),  # noqa: B008
    service: ModelService = Depends(get_model_service),  # noqa: B008
) -> ClassifyResponse:
    """Ingest image upload, run model inference with timeout resilience, and return classification."""
    # 1. Read uploaded image bytes and immediately release file descriptor
    try:
        try:
            image_bytes = await file.read()
        except Exception as exc:
            logger.error("Failed to read uploaded file stream: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to read the uploaded image stream.",
            ) from exc
    finally:
        await file.close()

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    # 2. Run model inference in bounded worker threadpool with timeout protection
    timeout_seconds = getattr(settings, "INFERENCE_TIMEOUT_SECONDS", 10.0)
    try:
        prediction = await inference_runner.run(
            service.predict, image_bytes, timeout_seconds
        )
    except InferenceBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inference capacity is busy. Please retry shortly.",
            headers={"Retry-After": "1"},
        ) from exc
    except TimeoutError as exc:
        logger.error("Inference request timed out after %.2f seconds", timeout_seconds)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Inference request timed out after {timeout_seconds:.1f}s.",
        ) from exc
    except IMAGE_DECODE_ERRORS as exc:
        logger.warning("Invalid or corrupted image payload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not read the image. The file may be corrupted, oversized, or has an invalid format.",
        ) from exc
    except (RuntimeError, MemoryError) as exc:
        logger.error("Model inference runtime execution failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inference engine temporarily unavailable or execution failed.",
        ) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected classification pipeline error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference pipeline encountered an unexpected error.",
        ) from None

    # 3. Post-inference defensive processing
    try:
        label = str(prediction.get("category", "")).strip().lower()
        item_name = prediction.get("item_name") or label.title()
        category = LABEL_TO_CATEGORY.get(label, "landfill")
        guidance = get_disposal_guidance(category, item_name, location)
        notes = guidance.get("notes", "")
        city_rule = get_category_rule(category, location)
        if city_rule:
            clean_notes = notes.strip().lower()
            clean_rule = city_rule.strip().lower()
            if clean_rule not in clean_notes and clean_notes not in clean_rule:
                separator = " " if notes.endswith(".") else ". "
                notes = f"{notes}{separator}Local rules: {city_rule}"
        bin_color = BIN_COLORS.get(category, "Green")

        # 4. Map alternative candidates through taxonomy normalization, filtering duplicates
        raw_alternatives = prediction.get("alternatives") or []
        alternatives: list[ClassificationAlternative] = []
        seen_categories: set[str] = {category}

        for alt in raw_alternatives:
            if not isinstance(alt, dict):
                continue
            raw_cat = str(alt.get("category", "")).strip().lower()
            mapped_cat = LABEL_TO_CATEGORY.get(raw_cat, raw_cat)
            if mapped_cat in ALLOWED_CATEGORIES and mapped_cat not in seen_categories:
                conf = alt.get("confidence")
                if conf is None or not isinstance(conf, (int, float)):
                    continue
                bounded_conf = max(0.0, min(1.0, float(conf)))
                alternatives.append(
                    ClassificationAlternative(
                        category=mapped_cat,
                        confidence=round(bounded_conf, 4),
                    )
                )
                seen_categories.add(mapped_cat)

        raw_conf = prediction.get("confidence", 0.0)
        primary_conf = float(raw_conf) if isinstance(raw_conf, (int, float)) else 0.0
        primary_conf = max(0.0, min(1.0, primary_conf))

        # 5. Build validated response payload
        return ClassifyResponse(
            item_name=item_name,
            category=category,
            confidence=round(primary_conf, 4),
            location=location.lower(),
            disposal_tip=get_disposal_tip(category, item_name, location),
            bin_color=bin_color,
            bin=f"{bin_color} {category.capitalize()} Bin",
            disposal_tips=DisposalTip(
                action=guidance["action"],
                bin_type=guidance["bin_type"],
                notes=notes,
            ),
            alternatives=alternatives,
        )
    except Exception:
        logger.exception("Failed to build classification response payload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error constructing classification response.",
        ) from None

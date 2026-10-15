"""Local image upload handling for the Week 1 sandbox route."""

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings

UPLOAD_DIR = Path(os.getenv("SORTIFY_UPLOAD_DIR", "temp_uploads"))
_CHUNK_BYTES = 1024 * 1024


def upload_byte_limit() -> int:
    return settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def safe_filename(name: str | None) -> str:
    """Keep only the final path segment so uploads cannot escape the directory."""
    if name is None or not str(name).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )
    base = str(name).replace("\\", "/").split("/")[-1].strip()
    if base in {"", ".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )
    return base


async def store_image_upload(
    file: UploadFile,
    dest_dir: Path | None = None,
    max_bytes: int | None = None,
) -> dict:
    """Stream an image to disk and return the Week 1 receipt payload."""
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Image required.",
        )

    filename = safe_filename(file.filename)
    directory = dest_dir if dest_dir is not None else UPLOAD_DIR
    limit = max_bytes if max_bytes is not None else upload_byte_limit()
    destination = directory / filename
    size = 0

    try:
        directory.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as buffer:
            while True:
                chunk = await file.read(_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Payload too large. File exceeds {limit} bytes.",
                    )
                buffer.write(chunk)
        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file.",
            )
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store upload.",
        ) from exc
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return {"status": "received", "filename": filename, "size_bytes": size}

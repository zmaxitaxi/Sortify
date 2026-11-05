"""Validate parsed multipart image uploads before classification."""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from backend.app.core.config import settings

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_RIFF = b"RIFF"
WEBP_MARKER = b"WEBP"


def _measure_file_size(file: UploadFile) -> int:
    """Measure disk-backed uploads in a worker when size metadata is absent."""
    file.file.seek(0, 2)
    return file.file.tell()


def get_max_upload_bytes() -> int:
    """Calculate maximum upload size limit in bytes from settings."""
    mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    return mb * 1024 * 1024


def normalize_content_type(raw_type: str | None) -> str:
    """Extract and normalize MIME type, stripping RFC parameters and aliases."""
    if not raw_type:
        return ""
    base_type = raw_type.split(";")[0].strip().lower()
    if base_type == "image/jpg":
        return "image/jpeg"
    return base_type


async def _reject(file: UploadFile, status_code: int, detail: str) -> None:
    """Safely close file descriptor before raising HTTPException to prevent resource leaks."""
    try:
        await file.close()
    except OSError:
        pass
    raise HTTPException(status_code=status_code, detail=detail)


async def validate_image_payload(
    file: UploadFile,
    max_bytes: int | None = None,
    return_bytes: bool = False,
) -> UploadFile | bytes:
    """Core image validation engine.

    Checks:
    1. Content-Type MIME header in ALLOWED_TYPES (with parameter stripping).
    2. Non-empty file size (must be > 0 bytes).
    3. Payload size does not exceed limit.
    4. Image magic bytes (sniffed non-blockingly).
    5. Extension match (if filename is provided).

    Returns:
        UploadFile (with seek pointer reset to 0) or bytes if return_bytes=True.
    """
    limit = max_bytes if max_bytes is not None else get_max_upload_bytes()

    # 1. Validate and normalize content type header
    content_type = normalize_content_type(file.content_type)
    if content_type not in ALLOWED_TYPES:
        await _reject(
            file,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported media type '{file.content_type}'. Image required (JPEG, PNG, WebP).",
        )

    # 2. Check total file size non-blockingly
    size = getattr(file, "size", None)
    if size is None:
        size = await run_in_threadpool(_measure_file_size, file)
    await file.seek(0)

    if size == 0:
        await _reject(
            file,
            status.HTTP_400_BAD_REQUEST,
            "Empty file upload.",
        )

    if size > limit:
        limit_mb = limit / (1024 * 1024)
        await _reject(
            file,
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds maximum upload limit of {limit_mb:.0f}MB.",
        )

    # 3. Magic byte inspection
    header = await file.read(12)
    await file.seek(0)

    is_jpeg = header.startswith(JPEG_MAGIC)
    is_png = header.startswith(PNG_MAGIC)
    is_webp = (
        header.startswith(WEBP_RIFF)
        and len(header) >= 12
        and header[8:12] == WEBP_MARKER
    )

    if not (is_jpeg or is_png or is_webp):
        await _reject(
            file,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "File signature mismatch. Contents do not match a valid JPEG, PNG, or WebP image.",
        )

    # Prevent file extension / MIME type spoofing
    if is_jpeg and content_type != "image/jpeg":
        await _reject(
            file,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "MIME type does not match JPEG file signature.",
        )
    if is_png and content_type != "image/png":
        await _reject(
            file,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "MIME type does not match PNG file signature.",
        )
    if is_webp and content_type != "image/webp":
        await _reject(
            file,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "MIME type does not match WebP file signature.",
        )

    # 4. Prevent file extension spoofing if filename is provided
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            await _reject(
                file,
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"File extension '{ext}' is unsupported. Must be .jpg, .jpeg, .png, or .webp.",
            )
        if ext in {".jpg", ".jpeg"} and not is_jpeg:
            await _reject(
                file,
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "File extension does not match JPEG content.",
            )
        if ext == ".png" and not is_png:
            await _reject(
                file,
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "File extension does not match PNG content.",
            )
        if ext == ".webp" and not is_webp:
            await _reject(
                file,
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "File extension does not match WebP content.",
            )

    if return_bytes:
        contents = await file.read()
        await file.seek(0)
        return contents

    return file


async def validate_image_upload(
    file: UploadFile,
) -> UploadFile:
    """FastAPI route dependency that validates uploaded multipart image.

    Exposes ONLY the file parameter to FastAPI dependency injection,
    preventing query parameter pollution, DoS limit bypass, and 500 crash bugs.
    """
    await validate_image_payload(file, return_bytes=False)
    return file

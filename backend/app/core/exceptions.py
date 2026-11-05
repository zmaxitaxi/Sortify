"""Public application errors and safe, consistent API exception responses."""

import logging
from http import HTTPStatus
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)
INTERNAL_MESSAGE = "An unexpected error occurred. Please try again."


class ErrorResponse(BaseModel):
    error: Literal[True] = True
    code: str
    message: str


ERROR_RESPONSES = {
    code: {"model": ErrorResponse}
    for code in (400, 401, 404, 405, 413, 415, 422, 500, 503, 504)
}


class SortifyException(Exception):
    """An application error whose message is safe to return to clients."""

    def __init__(self, message: str, code: str = "BAD_REQUEST", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidImageError(SortifyException):
    def __init__(self, message: str = "Unsupported or corrupted image file."):
        super().__init__(message, "INVALID_IMAGE_FORMAT", 415)


class PayloadTooLargeError(SortifyException):
    def __init__(self, message: str = "Uploaded image exceeds maximum size limit."):
        super().__init__(message, "PAYLOAD_TOO_LARGE", 413)


class ModelInferenceError(SortifyException):
    def __init__(self, message: str = "Model inference failed. Please try again."):
        super().__init__(message, "MODEL_INFERENCE_ERROR", 500)


class EntityNotFoundError(SortifyException):
    def __init__(self, message: str = "Requested resource was not found."):
        super().__init__(message, "ENTITY_NOT_FOUND", 404)


def error_response(status_code: int, code: str, message: str, headers=None):
    return JSONResponse(
        status_code=status_code,
        content={"error": True, "code": code, "message": message},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Cover domain errors, framework errors, validation, and unexpected failures."""

    @app.exception_handler(SortifyException)
    async def handle_sortify_exception(request: Request, exc: SortifyException):
        logger.log(
            logging.ERROR if exc.status_code >= 500 else logging.WARNING,
            "Sortify error [%s] at %s: %s",
            exc.code,
            request.url.path,
            exc.message,
            exc_info=exc if exc.status_code >= 500 else None,
        )
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        codes = {
            404: "ENTITY_NOT_FOUND",
            413: "PAYLOAD_TOO_LARGE",
            415: "INVALID_IMAGE_FORMAT",
            422: "VALIDATION_ERROR",
            500: "INTERNAL_SERVER_ERROR",
        }
        try:
            default_code = HTTPStatus(exc.status_code).name
        except ValueError:
            default_code = "HTTP_ERROR"
        message = str(exc.detail)
        if exc.status_code >= 500:
            logger.error("HTTP failure at %s", request.url.path, exc_info=exc)
            message = {
                503: "Service temporarily unavailable. Please try again.",
                504: "The request timed out. Please try again.",
            }.get(exc.status_code, INTERNAL_MESSAGE)
        return error_response(
            exc.status_code,
            codes.get(exc.status_code, default_code),
            message,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request, exc: RequestValidationError
    ):
        # Never echo request bodies, raw inputs, or validator exception contexts.
        return error_response(422, "VALIDATION_ERROR", "Request validation failed.")

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception):
        logger.error("Unhandled exception at %s", request.url.path, exc_info=exc)
        return error_response(500, "INTERNAL_SERVER_ERROR", INTERNAL_MESSAGE)

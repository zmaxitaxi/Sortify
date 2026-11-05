---
title: "feat(backend): Centralized Exception Handling & Server Stability"
labels: ["sprint-2", "backend", "resilience"]
subteam: "backend"
deliverable_branch: "feat/backend/<claimant>/centralized-exceptions"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-centralized-exception-handling--server-stability"
---

## 🎯 Objective
Ensure the server never crashes, leaks internal Python tracebacks, or exposes sensitive system information when receiving malformed, corrupted, or oversized inputs.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Centralized Exception Handling & Server Stability](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-centralized-exception-handling--server-stability)
- **Backend Subteam Plan:** [Backend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_backend.md#ticket-centralized-exception-handling--server-stability)
- **Starter Code Reference:** [starter_code/updated_backend_code.md#ticket-centralized-exception-handlers](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_backend_code.md#ticket-centralized-exception-handlers)

## 📁 Expected Files
- `backend/app/core/exceptions.py`
- `backend/app/main.py` (handler registration)
- `backend/tests/test_exceptions.py`

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/backend/<claimant>/centralized-exceptions`
- **Custom Exceptions (`backend/app/core/exceptions.py`):**
  - Define `SortifyException(message, code, status_code)` base class.
  - Define specific subclasses: `InvalidImageError` (HTTP 415), `PayloadTooLargeError` (HTTP 413), `ModelInferenceError` (HTTP 500), and `EntityNotFoundError` (HTTP 404).
- **Global Handlers (`register_exception_handlers` in `backend/app/main.py`):**
  - Register exception handler for `SortifyException` returning standard JSON:
    `{"error": true, "code": exc.code, "message": exc.message}`
  - Register catch-all exception handler for unhandled `Exception` logging the traceback internally and returning safe HTTP 500 JSON:
    `{"error": true, "code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred. Please try again."}`
  - Uniform handling for payload size limits (HTTP 413) and unsupported media formats (HTTP 415).
- **Automated Tests (`backend/tests/test_exceptions.py`):**
  - Assert that custom exceptions return proper status codes and JSON schemas.
  - Assert that unhandled exceptions do not return raw HTML tracebacks.
- **Verification:**
  - Send corrupted files and oversized payloads to the server; verify clean JSON error responses return without server crashes.

---

## 💻 Starter Scaffold

### `backend/app/core/exceptions.py`
```python
"""Custom exceptions and centralized error handlers for Sortify."""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class SortifyException(Exception):
    """Base exception for application-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "BAD_REQUEST",
        status_code: int = 400,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidImageError(SortifyException):
    def __init__(self, message: str = "Unsupported or corrupted image file"):
        super().__init__(message=message, code="INVALID_IMAGE_FORMAT", status_code=415)


class PayloadTooLargeError(SortifyException):
    def __init__(
        self, message: str = "Uploaded image exceeds maximum size limit (10MB)"
    ):
        super().__init__(message=message, code="PAYLOAD_TOO_LARGE", status_code=413)


def register_exception_handlers(app: FastAPI):
    """Registers application-wide centralized exception handlers."""

    @app.exception_handler(SortifyException)
    async def handle_sortify_exception(request: Request, exc: SortifyException):
        logger.warning(
            f"SortifyException [{exc.code}] at {request.url.path}: {exc.message}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "code": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception):
        logger.error(f"Unhandled exception at {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        )
```

### Integration in `backend/app/main.py`
```python
from backend.app.core.exceptions import register_exception_handlers

# Register after creating FastAPI instance
register_exception_handlers(app)
```

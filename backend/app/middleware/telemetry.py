"""Request logging middleware.

Log line format from the implementation plan:
``[METHOD] /path - Client IP - Status Code - Elapsed Time (ms)``
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("sortify.api")


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        client_ip = request.client.host if request and request.client else "unknown"
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"
        try:
            response = await call_next(request)
        except Exception:
            self._log(request.method, path, client_ip, 500, _elapsed_ms(start))
            raise
        self._log(
            request.method,
            path,
            client_ip,
            response.status_code,
            _elapsed_ms(start),
        )
        return response

    @staticmethod
    def _log(
        method: str, path: str, client_ip: str, status_code: int, elapsed_ms: float
    ):
        try:
            logger.info(
                "[%s] %s - %s - %s - %.1fms",
                method,
                path,
                client_ip,
                status_code,
                elapsed_ms,
            )
        except Exception:
            logger.exception("request log failed")


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000

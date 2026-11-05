"""Bound actual inference work independently of request cancellation."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Any


class InferenceBusyError(RuntimeError):
    """Raised when all inference workers are occupied."""


class InferenceRunner:
    """Admit at most max_workers jobs, without an unbounded executor queue."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="sortify-inference"
        )
        self._slots = BoundedSemaphore(max_workers)

    async def run(
        self, predict: Callable[[bytes], Any], image_bytes: bytes, timeout: float
    ) -> Any:
        if not self._slots.acquire(blocking=False):
            raise InferenceBusyError("All inference workers are occupied")
        try:
            worker = self._executor.submit(predict, image_bytes)
        except BaseException:
            self._slots.release()
            raise
        # A timed-out/disconnected request cannot free a still-running worker's slot.
        worker.add_done_callback(lambda _: self._slots.release())
        result = asyncio.wrap_future(worker)
        # Retrieve late errors too, after the HTTP request has stopped awaiting us.
        result.add_done_callback(self._consume_exception)
        return await asyncio.wait_for(asyncio.shield(result), timeout=timeout)

    @staticmethod
    def _consume_exception(result: asyncio.Future) -> None:
        if not result.cancelled():
            result.exception()

    def shutdown(self) -> None:
        """Drain workers when disposing an isolated runner."""
        self._executor.shutdown(wait=True, cancel_futures=True)


inference_runner = InferenceRunner()

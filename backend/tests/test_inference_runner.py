"""Inference limits must survive HTTP timeouts and request cancellation."""

import asyncio
import io
import threading

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.routers import classify
from backend.app.services.inference_runner import InferenceBusyError, InferenceRunner


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_timeout_setting_requires_positive_finite_deadline(timeout):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, INFERENCE_TIMEOUT_SECONDS=timeout)


@pytest.mark.parametrize("stop", ["timeout", "cancel"])
def test_abandoned_request_keeps_worker_permit(stop):
    runner = InferenceRunner(max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def predict(_):
        started.set()
        if not release.wait(3):
            raise RuntimeError("test worker was not released")
        return "finished"

    async def scenario():
        request = asyncio.create_task(
            runner.run(predict, b"image", 0.05 if stop == "timeout" else 2)
        )
        assert await asyncio.to_thread(started.wait, 1)
        if stop == "cancel":
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
        else:
            with pytest.raises(TimeoutError):
                await request
        with pytest.raises(InferenceBusyError):
            await runner.run(predict, b"another", 1)
        release.set()
        for _ in range(100):
            try:
                assert (
                    await runner.run(lambda _: "recovered", b"image", 1) == "recovered"
                )
                break
            except InferenceBusyError:
                await asyncio.sleep(0.01)
        else:
            pytest.fail("worker permit was not recovered")

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        runner.shutdown()


def test_concurrent_http_timeouts_never_exceed_worker_limit(monkeypatch):
    runner = InferenceRunner(max_workers=4)
    release = threading.Event()
    lock = threading.Lock()
    active = peak = 0

    def slow_predict(self, _):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            if not release.wait(3):
                raise RuntimeError("test worker was not released")
            return {"category": "paper", "confidence": 0.9}
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(classify, "inference_runner", runner)
    monkeypatch.setattr(
        classify,
        "settings",
        classify.settings.model_copy(update={"INFERENCE_TIMEOUT_SECONDS": 0.05}),
    )
    monkeypatch.setattr(classify.ModelService, "predict", slow_predict)
    image = io.BytesIO()
    Image.new("RGB", (16, 16)).save(image, format="JPEG")

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:

            async def post():
                return await client.post(
                    "/api/classify",
                    files={"file": ("photo.jpg", image.getvalue(), "image/jpeg")},
                )

            responses = await asyncio.gather(*(post() for _ in range(12)))
            codes = [response.status_code for response in responses]
            assert codes.count(504) == 4
            assert codes.count(503) == 8
            with lock:
                assert active == peak == 4
            assert (await post()).status_code == 503
            release.set()
            for _ in range(100):
                response = await post()
                if response.status_code == 200:
                    break
                assert response.status_code == 503
                await asyncio.sleep(0.01)
            else:
                pytest.fail("inference did not recover after worker completion")

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        runner.shutdown()


def test_worker_error_releases_capacity():
    runner = InferenceRunner(max_workers=1)

    def fail(_):
        raise RuntimeError("model failed")

    async def scenario():
        with pytest.raises(RuntimeError, match="model failed"):
            await runner.run(fail, b"image", 1)
        assert await runner.run(lambda _: "recovered", b"image", 1) == "recovered"

    try:
        asyncio.run(scenario())
    finally:
        runner.shutdown()

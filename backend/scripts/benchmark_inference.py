"""CPU Inference Latency Benchmark for Sortify Classification Service.

Benchmarks model inference execution time across 20 synthetic images of varying
aspect ratios, resolutions, and formats.
"""

import io
import math
import statistics
import time
from typing import Any

import torch
from PIL import Image

from backend.app.services.model_service import ModelService, model_service

# 20 diverse test image specifications (aspect ratios, sizes, modes, formats)
BENCHMARK_IMAGE_SPECS: list[dict[str, Any]] = [
    # Standard square resolutions
    {"size": (224, 224), "mode": "RGB", "format": "JPEG", "desc": "Standard 224x224"},
    {"size": (256, 256), "mode": "RGB", "format": "JPEG", "desc": "Medium 256x256"},
    {"size": (512, 512), "mode": "RGB", "format": "JPEG", "desc": "High-res 512x512"},
    {"size": (64, 64), "mode": "RGB", "format": "JPEG", "desc": "Low-res 64x64"},
    {"size": (32, 32), "mode": "RGB", "format": "JPEG", "desc": "Tiny 32x32"},
    # Landscape aspect ratios
    {"size": (640, 480), "mode": "RGB", "format": "JPEG", "desc": "Landscape 4:3"},
    {"size": (800, 450), "mode": "RGB", "format": "JPEG", "desc": "Landscape 16:9"},
    {"size": (1200, 300), "mode": "RGB", "format": "JPEG", "desc": "Panoramic 4:1"},
    {"size": (1000, 100), "mode": "RGB", "format": "JPEG", "desc": "Extreme Wide 10:1"},
    {"size": (800, 600), "mode": "RGB", "format": "PNG", "desc": "PNG Landscape 4:3"},
    # Portrait aspect ratios
    {"size": (480, 640), "mode": "RGB", "format": "JPEG", "desc": "Portrait 3:4"},
    {"size": (450, 800), "mode": "RGB", "format": "JPEG", "desc": "Portrait 9:16"},
    {"size": (300, 1200), "mode": "RGB", "format": "JPEG", "desc": "Tall Vertical 1:4"},
    {"size": (100, 1000), "mode": "RGB", "format": "JPEG", "desc": "Extreme Tall 1:10"},
    {"size": (600, 800), "mode": "RGB", "format": "PNG", "desc": "PNG Portrait 3:4"},
    # Different color spaces and modes
    {"size": (224, 224), "mode": "RGBA", "format": "PNG", "desc": "RGBA 4-channel"},
    {"size": (400, 400), "mode": "RGBA", "format": "PNG", "desc": "RGBA Large"},
    {"size": (224, 224), "mode": "L", "format": "JPEG", "desc": "Grayscale 1-channel"},
    {"size": (500, 500), "mode": "L", "format": "JPEG", "desc": "Grayscale Large"},
    # Minimal edge cases
    {"size": (10, 10), "mode": "RGB", "format": "JPEG", "desc": "Micro image 10x10"},
]


def generate_test_image(
    size: tuple[int, int],
    mode: str = "RGB",
    img_format: str = "JPEG",
) -> bytes:
    """Generate in-memory synthetic image bytes with given parameters."""
    color: Any = (128, 128, 128)
    if mode == "RGBA":
        color = (120, 180, 240, 255)
    elif mode == "L":
        color = 128

    img = Image.new(mode, size, color=color)
    buffer = io.BytesIO()
    img.save(buffer, format=img_format)
    return buffer.getvalue()


def calculate_percentile(data: list[float], percentile: float) -> float:
    """Calculate the given percentile (0 to 100) from sorted list with boundary clamping."""
    if not data:
        return 0.0
    p = max(0.0, min(100.0, float(percentile)))
    k = (len(data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[int(f)] * (c - k)
    d1 = data[int(c)] * (k - f)
    return d0 + d1


def run_inference_benchmark(
    specs: list[dict[str, Any]] | None = None,
    warmup_runs: int = 2,
    force_cpu: bool = True,
    service: ModelService | None = None,
) -> dict[str, Any]:
    """Run inference benchmark across test image specifications.

    Args:
        specs: List of image configuration dictionaries. Defaults to 20 images.
        warmup_runs: Number of initial untimed warmup executions.
        force_cpu: Whether to force execution strictly on CPU.
        service: Custom ModelService instance to benchmark. Defaults to global instance.

    Returns:
        dict containing latency metrics and per-image execution times.
    """
    image_specs = specs or BENCHMARK_IMAGE_SPECS
    bench_service = service or model_service

    if force_cpu:
        bench_service.device = torch.device("cpu")
        if bench_service.model is not None:
            bench_service.model = bench_service.model.to("cpu")

    # Pre-generate image payloads
    image_payloads = [
        (spec, generate_test_image(spec["size"], spec["mode"], spec["format"]))
        for spec in image_specs
    ]

    # Warmup runs
    for _ in range(warmup_runs):
        if image_payloads:
            bench_service.predict(image_payloads[0][1])

    results: list[dict[str, Any]] = []
    latencies: list[float] = []

    for index, (spec, payload) in enumerate(image_payloads, 1):
        if bench_service.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()
        start = time.perf_counter()
        prediction = bench_service.predict(payload)
        if bench_service.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        latencies.append(elapsed_ms)
        results.append(
            {
                "index": index,
                "description": spec["desc"],
                "size": spec["size"],
                "mode": spec["mode"],
                "format": spec["format"],
                "latency_ms": round(elapsed_ms, 2),
                "predicted_category": prediction.get("category"),
                "confidence": prediction.get("confidence"),
                "is_mock": prediction.get("is_mock", False),
            }
        )

    sorted_latencies = sorted(latencies)
    mean_ms = statistics.mean(sorted_latencies) if sorted_latencies else 0.0
    stdev_ms = statistics.stdev(sorted_latencies) if len(sorted_latencies) > 1 else 0.0
    is_mock = any(res.get("is_mock", False) for res in results)

    metrics = {
        "count": len(sorted_latencies),
        "total_ms": round(sum(sorted_latencies), 2),
        "min_ms": round(min(sorted_latencies), 2) if sorted_latencies else 0.0,
        "max_ms": round(max(sorted_latencies), 2) if sorted_latencies else 0.0,
        "mean_ms": round(mean_ms, 2),
        "median_ms": round(statistics.median(sorted_latencies), 2)
        if sorted_latencies
        else 0.0,
        "p90_ms": round(calculate_percentile(sorted_latencies, 90), 2),
        "p95_ms": round(calculate_percentile(sorted_latencies, 95), 2),
        "p99_ms": round(calculate_percentile(sorted_latencies, 99), 2),
        "stdev_ms": round(stdev_ms, 2),
        "device": str(bench_service.device),
        "is_mock": is_mock,
        "individual_results": results,
    }
    return metrics


def print_benchmark_report(metrics: dict[str, Any]) -> None:
    """Print formatted summary report table to stdout."""
    device_label = metrics.get("device", "cpu").upper()
    print("=" * 80)
    print(f" SORTIFY INFERENCE BENCHMARK ({metrics['count']} Images on {device_label})")
    if metrics.get("is_mock"):
        print(
            " [NOTICE] Execution completed in Mock/Fallback Mode (weights file not loaded)."
        )
    print("=" * 80)
    print(
        f"{'#':<3} | {'Description':<24} | {'Size':<12} | {'Mode':<5} | {'Latency':<10} | {'Category':<10}"
    )
    print("-" * 80)
    for res in metrics["individual_results"]:
        size_str = f"{res['size'][0]}x{res['size'][1]}"
        print(
            f"{res['index']:<3} | {res['description']:<24} | {size_str:<12} | {res['mode']:<5} | {res['latency_ms']:>7.2f} ms | {res['predicted_category']!s:<10}"
        )
    print("-" * 80)
    print(f" SUMMARY METRICS ({device_label}):")
    print(f"  - Total Elapsed Time : {metrics['total_ms']:.2f} ms")
    print(
        f"  - Mean Latency        : {metrics['mean_ms']:.2f} ms (+/- {metrics['stdev_ms']:.2f} ms)"
    )
    print(f"  - Median (p50)        : {metrics['median_ms']:.2f} ms")
    print(f"  - 90th Percentile     : {metrics['p90_ms']:.2f} ms")
    print(f"  - 95th Percentile     : {metrics['p95_ms']:.2f} ms")
    print(f"  - 99th Percentile     : {metrics['p99_ms']:.2f} ms")
    print(
        f"  - Min / Max Latency   : {metrics['min_ms']:.2f} ms / {metrics['max_ms']:.2f} ms"
    )
    print("=" * 80)


if __name__ == "__main__":
    report = run_inference_benchmark()
    print_benchmark_report(report)

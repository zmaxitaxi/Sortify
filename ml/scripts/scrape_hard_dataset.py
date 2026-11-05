"""Sortify — Authentic Waste Dataset Scraper & Curator.

Downloads and curates authentic in-the-wild "hard" waste photos across the 5 standard
Sortify classes (compost, glass, landfill, paper, plastic) sourced directly from the
peer-reviewed RealWaste dataset (hosted on Hugging Face / UCI ML Repository).

Unlike web search scrapers that accidentally capture historical manuscripts, botanical
illustrations, and scenic landscapes, every single image in RealWaste was captured at an
operational municipal waste facility, ensuring genuine real-world waste items (crushed cans,
soiled food organics, broken glass, crumpled cardboard, and plastic containers).

Usage:
    python ml/scripts/scrape_hard_dataset.py --target-per-class 40 --output-dir data/raw_expanded
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Standard Sortify classes
CLASSES = ["compost", "glass", "landfill", "paper", "plastic"]

# Hugging Face RealWaste dataset metadata and file endpoints
HF_API_URL = "https://huggingface.co/api/datasets/shahzaibvohra/realwaste"
HF_RAW_BASE_URL = "https://huggingface.co/datasets/shahzaibvohra/realwaste/resolve/main"

# Mapping from Sortify classes to RealWaste source category distributions
CLASS_MAPPING: dict[str, list[tuple[str, int]]] = {
    "compost": [("Food Organics", 40)],
    "glass": [("Glass", 40)],
    "landfill": [("Metal", 20), ("Miscellaneous Trash", 20)],
    "paper": [("Cardboard", 20), ("Paper", 20)],
    "plastic": [("Plastic", 40)],
}

DEFAULT_USER_AGENT = (
    "SortifyDatasetCurator/2.0 (academic research; cv-team@sortify.org) Python/3.13"
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scrape_hard_dataset")


def fetch_realwaste_file_list(
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, list[str]]:
    """Retrieve the list of JPEG files grouped by RealWaste category prefix."""
    req = urllib.request.Request(HF_API_URL, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as err:
        logger.error("Failed to query RealWaste metadata from Hugging Face: %s", err)
        raise

    grouped: dict[str, list[str]] = {}
    for item in data.get("siblings", []):
        filename = item.get("rfilename", "")
        if not filename.lower().endswith(".jpg") or "_" not in filename:
            continue
        prefix = filename.split("_")[0]
        grouped.setdefault(prefix, []).append(filename)

    logger.info(
        "Successfully retrieved RealWaste index: %d categories indexed.",
        len(grouped),
    )
    return grouped


def download_and_validate_image(
    filename: str,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Image.Image | None:
    """Download image from Hugging Face and validate byte integrity."""
    encoded_name = urllib.parse.quote(filename)
    url = f"{HF_RAW_BASE_URL}/{encoded_name}"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        logger.debug("Failed downloading %s: %s", filename, err)
        return None

    try:
        with Image.open(io.BytesIO(content)) as raw_img:
            raw_img.verify()

        with Image.open(io.BytesIO(content)) as img:
            if img.mode != "RGB":
                return img.convert("RGB")
            return img.copy()
    except (UnidentifiedImageError, OSError, ValueError) as err:
        logger.debug("Image validation failed for %s: %s", filename, err)
        return None


def curate_realwaste_dataset(
    target_per_class: int = 40,
    output_dir: Path = Path("data/raw_expanded"),
    clean_existing: bool = True,
) -> dict[str, int]:
    """Curate authentic trash dataset from RealWaste for the 5 Sortify classes."""
    if clean_existing and output_dir.exists():
        logger.info(
            "Cleaning existing directory '%s' to purge non-trash images...", output_dir
        )
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "dataset_manifest.json"
    manifest: list[dict[str, Any]] = []
    summary_counts: dict[str, int] = {}

    file_index = fetch_realwaste_file_list()

    for category in CLASSES:
        cat_dir = output_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        sources = CLASS_MAPPING.get(category, [])

        saved_count = 0
        logger.info("Curating category [%s]...", category)

        for src_prefix, quota in sources:
            available_files = file_index.get(src_prefix, [])
            if not available_files:
                logger.warning("No files found for source prefix '%s'", src_prefix)
                continue

            # Scale quota if target_per_class is customized
            allocated = round(quota * (target_per_class / 40.0))
            class_saved_from_src = 0

            for orig_name in available_files:
                if class_saved_from_src >= allocated or saved_count >= target_per_class:
                    break

                img = download_and_validate_image(orig_name)
                if img is None:
                    continue

                saved_count += 1
                class_saved_from_src += 1
                file_name = f"{category}_{saved_count:04d}.jpg"
                file_path = cat_dir / file_name

                img.save(file_path, "JPEG", quality=92)
                manifest.append(
                    {
                        "filename": file_name,
                        "category": category,
                        "source_dataset": "RealWaste (UCI / HF)",
                        "original_filename": orig_name,
                        "realwaste_class": src_prefix,
                        "width": img.width,
                        "height": img.height,
                    }
                )

                if saved_count % 10 == 0 or saved_count == target_per_class:
                    logger.info(
                        "[%s] Saved %d / %d images (%s: %d/%d)",
                        category,
                        saved_count,
                        target_per_class,
                        src_prefix,
                        class_saved_from_src,
                        allocated,
                    )

                time.sleep(0.05)

        summary_counts[category] = saved_count
        logger.info(
            "Finished [%s]: %d genuine waste photos saved.", category, saved_count
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_images": sum(summary_counts.values()),
                "target_per_class": target_per_class,
                "counts_by_class": summary_counts,
                "dataset_source": "RealWaste (authentic municipal landfill/waste facility)",
                "images": manifest,
            },
            f,
            indent=2,
        )

    logger.info("Manifest saved to %s", manifest_path)
    logger.info("Curated dataset summary: %s", summary_counts)
    return summary_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Curate authentic waste images across Sortify classes from RealWaste."
    )
    parser.add_argument(
        "--target-per-class",
        type=int,
        default=40,
        help="Number of images per class (default: 40, total 200).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw_expanded"),
        help="Target root directory (default: data/raw_expanded).",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not wipe existing directory before writing.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    curate_realwaste_dataset(
        target_per_class=args.target_per_class,
        output_dir=args.output_dir,
        clean_existing=not args.no_clean,
    )

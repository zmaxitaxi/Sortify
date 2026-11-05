"""Sortify — True In-The-Wild Waste Dataset Curator.

Builds an authentic, "hard" waste dataset by cropping verified bounding boxes
from TACO (Trash Annotations in Context) and incorporating real food organics.
Unlike single-background lab datasets, these images feature:
  - Real, diverse environments (sidewalks, grass, pavement, bins, tables)
  - Varied camera angles, distances, and natural outdoor/indoor lighting
  - Crushed, soiled, crumpled physical states
  - Authentic multi-material waste items

Classes: compost, glass, landfill, paper, plastic (40 each = 200 total).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import random
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLASSES = ["compost", "glass", "landfill", "paper", "plastic"]

TACO_ANNOTATIONS_URL = (
    "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"
)
HF_REALWASTE_BASE_URL = (
    "https://huggingface.co/datasets/shahzaibvohra/realwaste/resolve/main"
)

# TACO category mapping to Sortify classes
TACO_CLASS_MAPPING = {
    "glass": ["Glass bottle", "Broken glass", "Glass cup", "Glass jar"],
    "paper": [
        "Paper cup",
        "Corrugated carton",
        "Drink carton",
        "Meal carton",
        "Paper bag",
        "Normal paper",
        "Tissues",
    ],
    "plastic": [
        "Clear plastic bottle",
        "Disposable plastic cup",
        "Other plastic bottle",
        "Disposable food container",
        "Plastic lid",
    ],
    "landfill": [
        "Drink can",
        "Crisp packet",
        "Aluminium foil",
        "Plastic utensils",
        "Foam food container",
        "Foam cup",
        "Food Can",
    ],
}

DEFAULT_USER_AGENT = (
    "SortifyDatasetCurator/3.0 (academic research; cv-team@sortify.org) Python/3.13"
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("curate_wild_dataset")


def load_taco_data(
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[dict[int, Any], list[dict[str, Any]]]:
    """Fetch TACO annotations and build category lookup."""
    logger.info("Fetching TACO annotation database...")
    req = urllib.request.Request(
        TACO_ANNOTATIONS_URL, headers={"User-Agent": user_agent}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    images = {img["id"]: img for img in data["images"]}
    cat_names = {c["id"]: c["name"] for c in data["categories"]}

    # Invert mapping
    target_to_sortify: dict[str, str] = {}
    for sortify_cls, taco_subcategories in TACO_CLASS_MAPPING.items():
        for name in taco_subcategories:
            target_to_sortify[name] = sortify_cls

    filtered_anns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    min_dim = 100

    for ann in data["annotations"]:
        name = cat_names.get(ann["category_id"])
        if name not in target_to_sortify:
            continue
        sortify_cls = target_to_sortify[name]
        bbox = ann["bbox"]
        if bbox[2] < min_dim or bbox[3] < min_dim:
            continue

        ann["sortify_class"] = sortify_cls
        ann["taco_category"] = name
        filtered_anns[sortify_cls].append(ann)

    for k, v in filtered_anns.items():
        logger.info("Found %d candidate in-the-wild crops for [%s]", len(v), k)

    return images, filtered_anns


def crop_taco_object(
    image_obj: Image.Image, bbox: list[float], margin_ratio: float = 0.15
) -> Image.Image | None:
    """Crop annotated object with contextual margins from in-the-wild background."""
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return None

    margin_x = w * margin_ratio
    margin_y = h * margin_ratio

    left = max(0, int(x - margin_x))
    top = max(0, int(y - margin_y))
    right = min(image_obj.width, int(x + w + margin_x))
    bottom = min(image_obj.height, int(y + h + margin_y))

    if right <= left or bottom <= top:
        return None

    cropped = image_obj.crop((left, top, right, bottom))
    if cropped.mode != "RGB":
        cropped = cropped.convert("RGB")
    return cropped


def download_image_bytes(
    url: str, user_agent: str = DEFAULT_USER_AGENT
) -> bytes | None:
    """Download image bytes from web."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        logger.debug("Failed download from %s: %s", url, err)
        return None


def curate_wild_dataset(
    target_per_class: int = 40,
    output_dir: Path = Path("data/raw_expanded"),
) -> dict[str, int]:
    """Curates genuine in-the-wild waste photos."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "dataset_manifest.json"
    manifest: list[dict[str, Any]] = []
    summary_counts: dict[str, int] = {}

    images_index, taco_anns = load_taco_data()
    cached_images: dict[int, Image.Image] = {}

    random.seed(42)

    # 1. Curate glass, landfill, paper, plastic from in-the-wild TACO crops
    for category in ["glass", "landfill", "paper", "plastic"]:
        cat_dir = output_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        candidates = list(taco_anns[category])
        random.shuffle(candidates)

        saved_count = 0
        logger.info("Curating in-the-wild crops for [%s]...", category)

        for ann in candidates:
            if saved_count >= target_per_class:
                break

            img_id = ann["image_id"]
            if img_id not in cached_images:
                img_meta = images_index.get(img_id)
                if not img_meta:
                    continue
                # Try tacodataset image URL first, fallback to flickr_url
                img_url = f"https://img.tacodataset.org/{img_meta['file_name']}"
                content = download_image_bytes(img_url)
                if not content and img_meta.get("flickr_url"):
                    content = download_image_bytes(img_meta["flickr_url"])
                if not content:
                    continue

                try:
                    loaded_img = Image.open(io.BytesIO(content))
                    cached_images[img_id] = loaded_img
                except (UnidentifiedImageError, OSError):
                    continue

            base_img = cached_images[img_id]
            crop = crop_taco_object(base_img, ann["bbox"])
            if crop is None or crop.width < 100 or crop.height < 100:
                continue

            saved_count += 1
            file_name = f"{category}_{saved_count:04d}.jpg"
            file_path = cat_dir / file_name

            crop.save(file_path, "JPEG", quality=92)
            manifest.append(
                {
                    "filename": file_name,
                    "category": category,
                    "source": "TACO (in-the-wild street/sidewalk/bin photo)",
                    "taco_subcategory": ann["taco_category"],
                    "width": crop.width,
                    "height": crop.height,
                }
            )

            if saved_count % 10 == 0 or saved_count == target_per_class:
                logger.info(
                    "[%s] Saved %d / %d in-the-wild crops",
                    category,
                    saved_count,
                    target_per_class,
                )

        summary_counts[category] = saved_count
        logger.info("Finished [%s]: %d images saved.", category, saved_count)

    # 2. Curate compost from RealWaste Food Organics
    cat_dir = output_dir / "compost"
    cat_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Curating real food waste photos for [compost]...")

    saved_count = 0
    # Use real food organics indices
    indices = list(range(1, 100))
    random.shuffle(indices)

    for idx in indices:
        if saved_count >= target_per_class:
            break
        src_name = f"Food Organics_{idx}.jpg"
        encoded = urllib.parse.quote(src_name)
        url = f"{HF_REALWASTE_BASE_URL}/{encoded}"
        content = download_image_bytes(url)
        if not content:
            continue

        try:
            with Image.open(io.BytesIO(content)) as raw:
                raw.verify()
            with Image.open(io.BytesIO(content)) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                saved_count += 1
                file_name = f"compost_{saved_count:04d}.jpg"
                file_path = cat_dir / file_name
                img.save(file_path, "JPEG", quality=92)

                manifest.append(
                    {
                        "filename": file_name,
                        "category": "compost",
                        "source": "RealWaste Food Organics",
                        "width": img.width,
                        "height": img.height,
                    }
                )
                if saved_count % 10 == 0 or saved_count == target_per_class:
                    logger.info(
                        "[compost] Saved %d / %d photos", saved_count, target_per_class
                    )
        except (UnidentifiedImageError, OSError, ValueError):
            continue

    summary_counts["compost"] = saved_count
    logger.info("Finished [compost]: %d images saved.", saved_count)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_images": sum(summary_counts.values()),
                "target_per_class": target_per_class,
                "counts_by_class": summary_counts,
                "description": "Authentic in-the-wild waste crops (TACO) and food organics",
                "images": manifest,
            },
            f,
            indent=2,
        )

    logger.info("Manifest saved to %s", manifest_path)
    logger.info("Final summary: %s", summary_counts)
    return summary_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curate in-the-wild waste dataset.")
    parser.add_argument("--target-per-class", type=int, default=40)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw_expanded"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    curate_wild_dataset(
        target_per_class=args.target_per_class, output_dir=args.output_dir
    )

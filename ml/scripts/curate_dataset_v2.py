"""Sortify — Dataset v2 Merger & Split Generator.

Merges baseline v1 images (data/sortify_5class) and in-the-wild expanded images
(data/raw_expanded), verifies distribution, and generates a unified, stratified
70% train / 15% val / 15% test split in data/processed_v2/ ready for training
and Google Drive release packaging.

Usage:
    python ml/scripts/curate_dataset_v2.py
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLASSES = ["compost", "glass", "landfill", "paper", "plastic"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("curate_dataset_v2")


def collect_images_from_dir(directory: Path) -> dict[str, list[Path]]:
    """Collect image paths grouped by class from a directory."""
    results: dict[str, list[Path]] = {c: [] for c in CLASSES}
    if not directory.exists():
        return results

    for cat in CLASSES:
        cat_dir = directory / cat
        if not cat_dir.is_dir():
            continue
        for p in cat_dir.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                results[cat].append(p)
    return results


def curate_and_split_v2(
    baseline_dir: Path = Path("data/sortify_5class"),
    expanded_dir: Path = Path("data/raw_expanded"),
    output_dir: Path = Path("data/processed_v2"),
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = 42,
) -> dict[str, dict[str, int]]:
    """Merges baseline and expanded images and produces stratified train/val/test splits."""
    logger.info("Collecting baseline images from %s...", baseline_dir)
    baseline_images = collect_images_from_dir(baseline_dir)

    logger.info("Collecting expanded in-the-wild images from %s...", expanded_dir)
    expanded_images = collect_images_from_dir(expanded_dir)

    combined_counts: dict[str, int] = {}
    combined_images: dict[str, list[Path]] = {}

    for cat in CLASSES:
        total_cat_imgs = baseline_images[cat] + expanded_images[cat]
        combined_images[cat] = total_cat_imgs
        combined_counts[cat] = len(total_cat_imgs)
        logger.info(
            "Category [%s]: %d baseline + %d expanded = %d total",
            cat,
            len(baseline_images[cat]),
            len(expanded_images[cat]),
            len(total_cat_imgs),
        )

    # Recreate output structure
    if output_dir.exists():
        logger.info("Clearing existing %s...", output_dir)
        shutil.rmtree(output_dir)

    split_counts: dict[str, dict[str, int]] = {
        s: {c: 0 for c in CLASSES} for s in ["train", "val", "test"]
    }
    for s in ["train", "val", "test"]:
        for cat in CLASSES:
            (output_dir / s / cat).mkdir(parents=True, exist_ok=True)

    for cat in CLASSES:
        cat_imgs = combined_images[cat][:]
        if not cat_imgs:
            continue

        rng = random.Random(random_state)
        rng.shuffle(cat_imgs)

        total_n = len(cat_imgs)
        val_n = round(total_n * val_ratio)
        test_n = round(total_n * test_ratio)

        val_imgs = cat_imgs[:val_n]
        test_imgs = cat_imgs[val_n : val_n + test_n]
        train_imgs = cat_imgs[val_n + test_n :]

        for split_name, img_list in [
            ("train", train_imgs),
            ("val", val_imgs),
            ("test", test_imgs),
        ]:
            split_dir = output_dir / split_name / cat
            for src_path in img_list:
                # Add prefix to ensure unique filenames when copying
                dst_name = f"{src_path.parent.name}_{src_path.name}"
                dst_path = split_dir / dst_name
                shutil.copy2(src_path, dst_path)
            split_counts[split_name][cat] = len(img_list)

    logger.info("Dataset v2 stratified split completed at %s!", output_dir)
    for s in ["train", "val", "test"]:
        logger.info(
            "  [%s split total: %d] %s",
            s,
            sum(split_counts[s].values()),
            split_counts[s],
        )

    return split_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and split Sortify dataset v2.")
    parser.add_argument(
        "--baseline-dir", type=Path, default=Path("data/sortify_5class")
    )
    parser.add_argument("--expanded-dir", type=Path, default=Path("data/raw_expanded"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed_v2"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    curate_and_split_v2(
        baseline_dir=args.baseline_dir,
        expanded_dir=args.expanded_dir,
        output_dir=args.output_dir,
    )

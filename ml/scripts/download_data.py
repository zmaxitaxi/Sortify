"""Sortify — Dataset Downloader Script.

Downloads and extracts the unified 5-class Sortify waste dataset
(paper, plastic, glass, compost, landfill) from Google Drive or a direct URL.

Usage:
    python ml/scripts/download_data.py
    python ml/scripts/download_data.py --url <GOOGLE_DRIVE_SHARE_LINK>
    python ml/scripts/download_data.py --file-id <GOOGLE_DRIVE_FILE_ID>
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

# Default Google Drive share link for the unified 5-class Sortify dataset:
DEFAULT_GDRIVE_URL = os.getenv(
    "SORTIFY_DATASET_GDRIVE_URL",
    "https://drive.google.com/file/d/1b37CM4vfEpdVjmISxXnMaL6B0J-Srtoj/view?usp=sharing",
)

CHUNK_SIZE = 1024 * 1024  # 1 MB


def extract_gdrive_file_id(url_or_id: str) -> str:
    """Extract a Google Drive file ID from a file or folder share URL."""
    clean_val = url_or_id.strip()

    # Check for direct file share /file/d/<file_id>/
    match = re.search(r"/file/d/([a-zA-Z0-9_-]{25,})", clean_val)
    if match:
        return match.group(1)

    # Check for generic /d/<file_id>/ pattern
    match = re.search(r"/d/([a-zA-Z0-9_-]{25,})", clean_val)
    if match:
        return match.group(1)

    # Check for query param ?id=<file_id>
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]{25,})", clean_val)
    if match:
        return match.group(1)

    # If it's a folder URL, query folder page to find the enclosed zip file ID
    folder_match = re.search(r"/folders/([a-zA-Z0-9_-]{25,})", clean_val)
    if folder_match:
        try:
            req = urllib.request.Request(
                clean_val,
                headers={"User-Agent": "Mozilla/5.0 (Sortify Dataset Downloader)"},
            )
            html = urllib.request.urlopen(req).read().decode("utf-8", errors="ignore")
            # Find file IDs in folder HTML
            file_match = re.search(r'ssk=[\'"][0-9]+:[^:]+:([a-zA-Z0-9_-]{25,})-', html)
            if file_match:
                return file_match.group(1)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    # If it's already a raw ID
    if re.match(r"^[a-zA-Z0-9_-]{25,}$", clean_val):
        return clean_val

    return clean_val


def download_from_google_drive(file_id: str, dest_path: Path) -> Path:
    """Download a file from Google Drive, handling confirmation prompts and redirects."""
    initial_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    urllib.request.install_opener(opener)

    req = urllib.request.Request(
        initial_url,
        headers={"User-Agent": "Mozilla/5.0 (Sortify Dataset Downloader)"},
    )

    response = opener.open(req)
    content_type = response.headers.get("Content-Type", "")

    # When Google Drive shows the "too large to scan for viruses" confirmation form
    if "text/html" in content_type:
        html = response.read().decode("utf-8", errors="ignore")

        # Parse form action (typically https://drive.usercontent.google.com/download)
        action_match = re.search(r'action="([^"]+)"', html)
        action_url = (
            action_match.group(1)
            if action_match
            else "https://drive.usercontent.google.com/download"
        )

        # Extract hidden input fields (id, export, confirm, uuid, etc.)
        inputs = re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]+)"', html)
        params = {name: val for name, val in inputs}
        if "id" not in params:
            params["id"] = file_id
        if "confirm" not in params:
            params["confirm"] = "t"
        if "export" not in params:
            params["export"] = "download"

        download_url = action_url + "?" + urllib.parse.urlencode(params)
        req2 = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0 (Sortify Dataset Downloader)"},
        )
        response = opener.open(req2)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    total_size = response.headers.get("Content-Length")
    total_bytes = int(total_size) if total_size and total_size.isdigit() else None

    downloaded_bytes = 0
    print(f"Downloading dataset to: {dest_path}")
    with open(dest_path, "wb") as f:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
            downloaded_bytes += len(chunk)
            if total_bytes:
                pct = (downloaded_bytes / total_bytes) * 100
                print(
                    f"\rProgress: {downloaded_bytes / (1024 * 1024):.1f} MB / "
                    f"{total_bytes / (1024 * 1024):.1f} MB ({pct:.1f}%)",
                    end="",
                    flush=True,
                )
            else:
                print(
                    f"\rDownloaded: {downloaded_bytes / (1024 * 1024):.1f} MB",
                    end="",
                    flush=True,
                )
    print("\nDownload complete!")

    return dest_path


def extract_archive(zip_path: Path, extract_to: Path) -> None:
    """Extract a zip archive into the target folder."""
    print(f"Extracting {zip_path.name} into {extract_to}...")
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    print("Extraction complete!")


def summarize_extracted_data(extract_dir: Path) -> None:
    """Scan and print the classes and image counts in the dataset."""
    print("\nDataset Summary:")
    classes = ["paper", "plastic", "glass", "compost", "landfill"]
    found_any = False
    for root, dirs, _ in os.walk(extract_dir):
        rel = Path(root).relative_to(extract_dir)
        if any(c in dirs for c in classes):
            print(f"Found class folders in: {rel or '.'}")
            found_any = True
            for c in classes:
                class_path = Path(root) / c
                if class_path.is_dir():
                    count = len(
                        [
                            f
                            for f in class_path.iterdir()
                            if f.is_file()
                            and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                        ]
                    )
                    print(f"  - {c:<10}: {count} images")

    if not found_any:
        print(f"Dataset extracted to {extract_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and extract the Sortify 5-class waste classification dataset."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_GDRIVE_URL,
        help="Google Drive share link or direct download URL.",
    )
    parser.add_argument(
        "--file-id",
        type=str,
        default="",
        help="Google Drive file ID (alternative to --url).",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=Path("data"),
        help="Directory to save and extract the dataset (default: data).",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded .zip file after extracting.",
    )
    args = parser.parse_args()

    target_id = ""
    if args.file_id:
        target_id = args.file_id.strip()
    elif args.url:
        target_id = extract_gdrive_file_id(args.url)

    if not target_id:
        print(
            "Error: No Google Drive link or file ID provided.\n"
            "Please provide --url <GDRIVE_LINK> or --file-id <ID>,\n"
            "or set the SORTIFY_DATASET_GDRIVE_URL environment variable."
        )
        sys.exit(1)

    dest_dir = args.dest_dir.resolve()
    zip_path = dest_dir / "sortify_5class_dataset.zip"

    try:
        download_from_google_drive(target_id, zip_path)
        extract_archive(zip_path, dest_dir)
        summarize_extracted_data(dest_dir)
        if not args.keep_zip and zip_path.exists():
            zip_path.unlink()
            print(f"Cleaned up temporary archive {zip_path.name}.")
    except (
        urllib.error.URLError,
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ) as e:
        print(f"Error downloading or extracting dataset: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

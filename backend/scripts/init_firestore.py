"""Seed Firestore with one dummy user and scan, or print them and exit.

Live writes need a service-account file at FIREBASE_CREDENTIALS_PATH. CI and
local checkouts without that file stay on the dry-run path.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.config import settings
from backend.app.services.firestore_records import (
    build_dummy_records,
    write_seed_records,
)


def credentials_path() -> Path:
    configured = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", settings.FIREBASE_CREDENTIALS_PATH
    )
    return Path(configured)


def credentials_available() -> bool:
    path = credentials_path()
    return path.is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Sortify Firestore collections")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Write to Firestore. Fails when credentials are missing.",
    )
    args = parser.parse_args(argv)
    records = build_dummy_records()

    if not args.live or not credentials_available():
        if args.live and not credentials_available():
            print(
                f"Firebase credentials not found at {credentials_path()}",
                file=sys.stderr,
            )
            return 2
        print(json.dumps({"mode": "dry-run", **records}, indent=2))
        return 0

    from backend.app.services.firebase import get_db

    written = write_seed_records(get_db(), records)
    print(
        "Firestore seed write complete "
        f"user={written['user_id']} scan={written['scan_id']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

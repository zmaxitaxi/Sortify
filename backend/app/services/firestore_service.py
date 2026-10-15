"""Firestore reads and writes for user scans.

The client is injected so tests can pass an in-memory fake. Production code
leaves it empty and connects on first use.
"""

import logging

from backend.app.services.firestore_records import validate_scan_document

logger = logging.getLogger("sortify.firestore")

MAX_SCAN_LIMIT = 100


class FirestoreServiceError(Exception):
    """Raised when a Firestore call fails after the payload is valid."""


class FirestoreService:
    def __init__(self, db=None):
        self._db = db

    def _client(self):
        if self._db is None:
            from backend.app.services.firebase import get_db

            self._db = get_db()
        return self._db

    def save_scan(self, user_id: str, scan_data: dict) -> str:
        """Write one scan under users/{user_id}/scans and return its id."""
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")
        payload = dict(scan_data or {})
        payload["user_id"] = user_id.strip()
        payload = validate_scan_document(payload, default_timestamp=True)
        try:
            doc_ref = (
                self._client()
                .collection("users")
                .document(payload["user_id"])
                .collection("scans")
                .document()
            )
            doc_ref.set(payload)
            return doc_ref.id
        except Exception as exc:
            logger.exception("Failed to save scan for user %s", user_id)
            raise FirestoreServiceError("Could not save scan") from exc

    def get_user_scans(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return that user's scans, newest timestamp first."""
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")  # noqa: TRY004
        if limit < 1 or limit > MAX_SCAN_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_SCAN_LIMIT}")
        try:
            return self._scan_rows(user_id.strip(), limit)
        except Exception as exc:
            logger.exception("Failed to read scans for user %s", user_id)
            raise FirestoreServiceError("Could not read scans") from exc

    def _scan_rows(self, user_id: str, limit: int | None) -> list[dict]:
        query = (
            self._client()
            .collection("users")
            .document(user_id)
            .collection("scans")
            .order_by("timestamp", direction="DESCENDING")
        )
        if limit is not None:
            query = query.limit(limit)
        rows = []
        for doc in query.stream():
            row = doc.to_dict() or {}
            row["scan_id"] = doc.id
            rows.append(row)
        return rows

    def get_user_stats(self, user_id: str) -> dict:
        """Return scan count, streak, and points. Missing users are zeros."""
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")
        uid = user_id.strip()
        try:
            snapshot = self._client().collection("users").document(uid).get()
            data = snapshot.to_dict() if snapshot.exists else {}
            if data is None:
                data = {}
            scans = self._scan_rows(uid, None)
        except Exception as exc:
            logger.exception("Failed to read stats for user %s", uid)
            raise FirestoreServiceError("Could not read user stats") from exc

        streak = data.get("current_streak", 0)
        points = data.get("points", 0)
        if isinstance(streak, bool) or not isinstance(streak, int) or streak < 0:
            streak = 0
        if isinstance(points, bool) or not isinstance(points, int) or points < 0:
            points = 0
        return {
            "user_id": uid,
            "total_scans": len(scans),
            "current_streak": streak,
            "points": points,
        }

---
title: "feat(backend): User Eco-Stats Aggregation Endpoint (GET /api/stats)"
labels: ["sprint-2", "backend", "feature"]
subteam: "backend"
deliverable_branch: "feat/backend/<claimant>/stats-aggregation-endpoint"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-user-eco-stats-aggregation-endpoint-get-apistats"
---

## 🎯 Objective
Aggregate user scan history to power the mobile Impact Dashboard with lifetime scan counts, eco-points, streak calculation, and category distribution.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: User Eco-Stats Aggregation Endpoint (GET /api/stats)](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-user-eco-stats-aggregation-endpoint-get-apistats)
- **Backend Subteam Plan:** [Backend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_backend.md#ticket-user-eco-stats-aggregation-endpoint-get-apistats)
- **Starter Code Reference:** [starter_code/updated_backend_code.md#ticket-eco-stats-aggregation-endpoint](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_backend_code.md#ticket-eco-stats-aggregation-endpoint)

## 📁 Expected Files
- `backend/app/routers/history.py` (or `backend/app/routers/stats.py`)
- `backend/app/schemas/stats.py` (or schema definitions in router)
- `backend/tests/test_stats.py`

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/backend/<claimant>/stats-aggregation-endpoint`
- **Stats Endpoint (`GET /api/stats/{user_id}`):**
  - Query user scan records via `history_service.get_user_history(user_id, limit=...)`.
  - Calculate:
    - `total_scans`: count of all recorded scans.
    - `eco_points`: points awarded (`total_scans * 10`).
    - `category_counts`: count of items per waste category (`compost`, `plastic`, `paper`, `glass`, `landfill`).
    - `current_streak`: integrated with `calculate_streak(timestamps)` from `streak_calculator.py`.
  - Return typed `UserStatsResponse` Pydantic model.
- **Unit Tests (`backend/tests/test_stats.py`):**
  - Test empty history returns 0 scans, 0 points, 0 streak, and empty category breakdown.
  - Test populated scan history accurately sums category counts and points.
  - Test response validation against Swagger / OpenAPI docs.
- **Verification:**
  - Execute `pytest backend/tests/test_stats.py -v`; confirm all aggregation tests pass green.

---

## 💻 Starter Scaffold

### `backend/app/routers/history.py` (Stats Route Addition)
```python
"""Stats router additions to backend/app/routers/history.py (or standalone stats router)."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.services.history_service import history_service
from backend.app.services.streak_calculator import calculate_streak

router = APIRouter(prefix="/stats", tags=["Stats"])


class UserStatsResponse(BaseModel):
    user_id: str = Field(..., description="Unique user or guest device UUID")
    total_scans: int = Field(
        ..., ge=0, description="Total lifetime waste items scanned"
    )
    eco_points: int = Field(
        ..., ge=0, description="Accumulated eco-points (10 per scan)"
    )
    current_streak: int = Field(
        ..., ge=0, description="Consecutive active daily sorting streak"
    )
    category_counts: dict[str, int] = Field(
        default_factory=dict, description="Count of items scanned per category"
    )


@router.get("/{user_id}", response_model=UserStatsResponse)
def get_user_stats(user_id: str):
    """Calculates eco-impact statistics for the user or device UUID."""
    history = history_service.get_user_history(user_id, limit=200)
    items = history.get("items", [])

    total = len(items)
    points = total * 10
    counts: dict[str, int] = {}
    timestamps: list[str] = []

    for item in items:
        cat = item.get("category", "other")
        counts[cat] = counts.get(cat, 0) + 1
        if "timestamp" in item and item["timestamp"]:
            timestamps.append(item["timestamp"])

    streak = calculate_streak(timestamps)

    return UserStatsResponse(
        user_id=user_id,
        total_scans=total,
        eco_points=points,
        current_streak=streak,
        category_counts=counts,
    )
```

### `backend/tests/test_stats.py`
```python
"""Unit tests for user eco-stats aggregation."""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.services.history_service import history_service

client = TestClient(app)


def test_get_user_stats_empty():
    user_id = "test_empty_user"
    response = client.get(f"/api/stats/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["total_scans"] == 0
    assert data["eco_points"] == 0
    assert data["current_streak"] == 0
    assert data["category_counts"] == {}


def test_get_user_stats_populated():
    user_id = "test_active_user"
    history_service.save_scan(
        {
            "scan_id": "s1",
            "user_id": user_id,
            "category": "plastic",
            "item_name": "Bottle",
            "bin": "Blue Recycling",
            "confidence": 0.95,
        }
    )
    history_service.save_scan(
        {
            "scan_id": "s2",
            "user_id": user_id,
            "category": "compost",
            "item_name": "Apple",
            "bin": "Green Compost",
            "confidence": 0.98,
        }
    )

    response = client.get(f"/api/stats/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_scans"] >= 2
    assert data["eco_points"] >= 20
    assert data["category_counts"].get("plastic", 0) >= 1
    assert data["category_counts"].get("compost", 0) >= 1
```

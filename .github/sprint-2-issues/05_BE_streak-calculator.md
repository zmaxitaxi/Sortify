---
title: "feat(backend): Timezone-Aware Daily Active Streak Calculator"
labels: ["sprint-2", "backend", "feature"]
subteam: "backend"
deliverable_branch: "feat/backend/<claimant>/streak-calculator"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-timezone-aware-daily-active-streak-calculator"
---

## 🎯 Objective
Accurately evaluate consecutive active sorting days while respecting the user's local timezone (`America/Los_Angeles` by default) to drive student habit formation and gamification.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Timezone-Aware Daily Active Streak Calculator](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-timezone-aware-daily-active-streak-calculator)
- **Backend Subteam Plan:** [Backend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_backend.md#ticket-timezone-aware-daily-active-streak-calculator)
- **Starter Code Reference:** [starter_code/updated_backend_code.md#ticket-daily-streak-calculator](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_backend_code.md#ticket-daily-streak-calculator)

## 📁 Expected Files
- `backend/app/services/streak_calculator.py`
- `backend/tests/test_streak_calculator.py`

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/backend/<claimant>/streak-calculator`
- **Streak Calculation Logic (`backend/app/services/streak_calculator.py`):**
  - Implement `calculate_streak(timestamps: list[str], user_tz: str = "America/Los_Angeles") -> int`:
    - Parse ISO 8601 timestamp strings.
    - Normalize to target timezone using Python standard library `zoneinfo.ZoneInfo`.
    - Deduplicate multiple scans occurring on the same local calendar date.
    - Check if the most recent scan is today or yesterday (grace period); if older than yesterday, streak resets to 0.
    - Walk backwards day-by-day counting unbroken consecutive days.
    - Gracefully ignore invalid, malformed, or null timestamps.
- **Unit Test Suite (`backend/tests/test_streak_calculator.py`):**
  - Test consecutive active days (e.g., today, yesterday, day before -> 3 days).
  - Test multiple scans in a single day (counts as 1 day towards streak).
  - Test missed day resets streak to 0.
  - Test scan today only (1 day streak).
  - Test scan yesterday only (1 day streak).
  - Test empty list or invalid timestamp inputs (returns 0 without exceptions).
- **Verification:**
  - Execute `pytest backend/tests/test_streak_calculator.py -v`; confirm 100% test pass rate.

---

## 💻 Starter Scaffold

### `backend/app/services/streak_calculator.py`
```python
"""Daily streak calculation helper."""

from datetime import datetime
from zoneinfo import ZoneInfo


def calculate_streak(
    timestamps: list[str], user_tz: str = "America/Los_Angeles"
) -> int:
    """Calculates consecutive active days from ISO 8601 timestamp strings.

    Args:
        timestamps: List of ISO format timestamp strings.
        user_tz: IANA timezone string (default: 'America/Los_Angeles').

    Returns:
        Integer representing active day streak.
    """
    if not timestamps:
        return 0

    try:
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")

    date_set = set()

    for ts in timestamps:
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts).astimezone(tz)
            date_set.add(dt.date())
        except Exception:
            continue

    if not date_set:
        return 0

    sorted_dates = sorted(date_set, reverse=True)
    today = datetime.now(tz).date()

    # Allow streak if latest scan is today or yesterday (grace period)
    diff_from_today = (today - sorted_dates[0]).days
    if diff_from_today > 1:
        return 0

    streak = 1
    for i in range(len(sorted_dates) - 1):
        if (sorted_dates[i] - sorted_dates[i + 1]).days == 1:
            streak += 1
        else:
            break

    return streak
```

### `backend/tests/test_streak_calculator.py`
```python
"""Unit tests for timezone-aware streak calculator."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from backend.app.services.streak_calculator import calculate_streak


def test_empty_timestamps_returns_zero():
    assert calculate_streak([]) == 0
    assert calculate_streak(["not-a-timestamp", "invalid"]) == 0


def test_single_scan_today():
    tz = ZoneInfo("America/Los_Angeles")
    now_iso = datetime.now(tz).isoformat()
    assert calculate_streak([now_iso]) == 1


def test_multiple_scans_same_day():
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(tz)
    ts1 = now.isoformat()
    ts2 = (now - timedelta(hours=2)).isoformat()
    assert calculate_streak([ts1, ts2]) == 1


def test_consecutive_days_streak():
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(tz)
    ts_today = now.isoformat()
    ts_yesterday = (now - timedelta(days=1)).isoformat()
    ts_two_days_ago = (now - timedelta(days=2)).isoformat()

    assert calculate_streak([ts_today, ts_yesterday, ts_two_days_ago]) == 3


def test_missed_day_resets_streak():
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(tz)
    ts_old = (now - timedelta(days=3)).isoformat()
    assert calculate_streak([ts_old]) == 0
```

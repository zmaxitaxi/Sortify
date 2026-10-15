# Firestore schema

Sortify stores people on `users/{uid}` and their classifications on a subcollection. The flat `scans/{scanId}` collection is the same scan document, kept so a console view can list every scan without walking users. `backend/scripts/init_firestore.py` seeds both. The read/write service uses the subcollection.

## `users/{uid}`

| Field | Type | Notes |
|---|---|---|
| `email` | string | Required, must contain `@` |
| `display_name` | string | Required |
| `created_at` | string | ISO-8601 timestamp |
| `current_streak` | int | `>= 0` |
| `total_scans` | int | `>= 0` |
| `points` | int | `>= 0` |

The document id is the Firebase uid. It is not copied into the fields above.

## `users/{uid}/scans/{scanId}` and `scans/{scanId}`

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | Same uid as the parent user |
| `image_url` | string | Empty until image storage exists |
| `predicted_category` | string | `compost`, `glass`, `landfill`, `paper`, or `plastic` |
| `item_name` | string | Falls back to the category |
| `confidence` | float | `0.0` through `1.0` |
| `location` | string | Municipality, default `berkeley` |
| `timestamp` | string | ISO-8601 UTC so newest-first ordering does not need a live sentinel |

## Seeding

Without a service account file the script prints the dummy records and exits 0:

```bash
python backend/scripts/init_firestore.py
```

`--live` writes them and exits 2 when `FIREBASE_CREDENTIALS_PATH` does not point at a file.

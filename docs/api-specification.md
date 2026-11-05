# Sortify API Specification

> **Version:** 1.0.0  
> **Author:** Janice (Backend Subteam)  
> **Status:** Active / Standardized Contract  
> **Base URL:** `http://localhost:8000` (Local) / `https://api.sortify.app` (Production)

---

## 1. Overview & Architectural Principles

The Sortify REST API decouples client applications (Expo / React Native mobile clients, web clients) from the core machine learning inference pipeline and Firestore persistence services.

### Core Principles
- **Predictable Error Contracts:** API HTTP 4xx and 5xx responses use `{"error": true, "code": "...", "message": "..."}`.
- **Standardized Bin Categories:** All sorting classifications are normalized to 5 core categories:
  - `compost` (Green)
  - `plastic` (Blue)
  - `paper` (Brown)
  - `glass` (Teal)
  - `landfill` (Gray)
- **High Performance:** Designed to satisfy the end-to-end latency budget (< 3.0s total roundtrip).

---

## 2. Authentication & Common Headers

### Request Headers
| Header | Type | Description | Required |
|---|---|---|---|
| `Authorization` | String | Firebase ID token in format `Bearer <token>` | Optional for guest endpoints (including `/api/history`), required for `/api/auth/me` |
| `Content-Type` | String | `application/json` for standard requests; `multipart/form-data` for image uploads | Required |
| `Accept` | String | `application/json` | Recommended |

### Standard Error Response Format
```json
{
  "error": true,
  "code": "INVALID_IMAGE_FORMAT",
  "message": "Unsupported or corrupted image file."
}
```

Clients should read `message` instead of the previous `detail` field and use
`code` for stable error handling. Request validation returns HTTP 422 with
`VALIDATION_ERROR` and a safe message, without echoing submitted values.
Unexpected errors return HTTP 500 with `INTERNAL_SERVER_ERROR`; Python exception
details and tracebacks are logged only on the server. Inference execution errors
return HTTP 500 with `MODEL_INFERENCE_ERROR`. Capacity limits remain HTTP 503
with `Retry-After`; inference timeouts remain HTTP 504. Framework errors such as
unknown routes use the same envelope. These responses apply before response
streaming starts; a failure after headers are sent cannot replace the response.

---

## 3. Endpoints

### 3.1 Health & Liveness Check
* **Endpoint:** `GET /health`
* **Description:** Verifies service availability, container readiness, and process health.
* **Authentication:** None

#### Response (HTTP 200 OK)
```json
{
  "status": "ok"
}
```

---

### 3.2 Waste Item Classification
* **Endpoint:** `POST /api/classify`
* **Description:** Ingests an image of a waste item, runs ML classification, evaluates municipal sorting rules, and returns bin destination recommendations.
* **Authentication:** Optional
* **Content-Type:** `multipart/form-data`

#### Request Parameters
- **Query Parameters:**
  - `location` *(string, optional, default: `"berkeley"`)*: Municipality identifier for location-specific disposal rules.
- **Form Data (Multipart):**
  - `file` *(binary upload, required)*: Waste item image (`JPEG`, `PNG`, `WEBP`). Maximum size: 10MB.

#### Response (HTTP 200 OK)
```json
{
  "item_name": "Plastic Water Bottle",
  "category": "plastic",
  "confidence": 0.94,
  "disposal_tip": "Empty liquids and replace cap before placing in blue recycling bin.",
  "bin_color": "Blue",
  "bin": "Blue Plastic Bin",
  "disposal_tips": {
    "action": "Recycle",
    "bin_type": "blue",
    "notes": "Rinse clean of residue."
  },
  "alternatives": [
    {
      "category": "landfill",
      "confidence": 0.04
    },
    {
      "category": "glass",
      "confidence": 0.02
    }
  ],
  "location": "berkeley"
}
```

#### Error Responses
- **HTTP 400 Bad Request:** Empty file or malformed multipart request.
- **HTTP 413 Payload Too Large:** File exceeds the 10MB upload limit.
- **HTTP 415 Unsupported Media Type:** Unsupported MIME/signature/extension, corrupt image, or unsafe image dimensions (`INVALID_IMAGE_FORMAT`).
- **HTTP 422 Unprocessable Entity:** Missing file field or invalid request parameters (`VALIDATION_ERROR`).
- **HTTP 500 Internal Server Error:** Model execution or unexpected pipeline failure; no private exception detail.
- **HTTP 503 Service Unavailable:** All inference workers are occupied; retry later.
- **HTTP 504 Gateway Timeout:** Inference exceeded the configured timeout.

---

### 3.3 Municipal Sorting Rules

#### 3.3.1 Get Rules for Specific Municipality
* **Endpoint:** `GET /api/rules/{city}`
* **Description:** Retrieves localized waste disposal guidelines and official city resources.
* **Authentication:** None

##### Path Parameters
- `city` *(string, required)*: Lowercase city name (e.g., `berkeley`, `san-francisco`, `oakland`).

##### Response (HTTP 200 OK)
```json
{
  "city": "berkeley",
  "rules": {
    "compost": "Food scraps, soiled paper, plant trimmings, BPI-certified compostable packaging.",
    "plastic": "Rigid plastics #1-#7, bottles, jugs, tubs. Must be empty and rinsed.",
    "paper": "Clean paper, cardboard, newsprint, magazines.",
    "glass": "Bottles and jars only. Rinse clean.",
    "landfill": "Styrofoam, plastic wrap, chip bags, hazardous materials."
  },
  "source_url": "https://berkeleyca.gov/city-services/trash-recycling"
}
```

#### 3.3.2 Get All Supported Cities
* **Endpoint:** `GET /api/rules`
* **Description:** Lists all municipalities with configured sorting rules.
* **Authentication:** None

##### Response (HTTP 200 OK)
```json
{
  "supported_cities": ["berkeley", "san-francisco", "oakland", "los-angeles"],
  "default_city": "berkeley"
}
```

---

### 3.4 Guest Scan History

History uses a randomly generated device UUID persisted by the mobile client.
This identifier selects the guest's records; it is not verified account
identity. Bearer login is not required. Keep the device UUID private and avoid
putting personal information in guest scan records.

#### 3.4.1 Retrieve Paginated Scan History
* **Endpoint:** `GET /api/history`
* **Query:** required `user_id` (UUID), optional `limit` (1–100, default 20),
  optional `cursor` (opaque `next_cursor` from the previous response).
* **Response:** `scans`, `limit`, `next_cursor`; no global total or numeric offset.
* Records are ordered by timestamp descending, then scan UUID descending.
  The extra record fetched by the service distinguishes a full final page from
  one with more results. Cursors are scoped to the device UUID.

```json
{
  "scans": [{
    "scan_id": "e60685c7-5dcc-42f0-9dc4-176b9676fec7",
    "user_id": "d993af39-f604-4426-abf7-fdd664918d15",
    "timestamp": "2026-10-28T08:00:00Z",
    "category": "plastic",
    "item_name": "Plastic Water Bottle",
    "confidence": 0.94,
    "location": "berkeley",
    "bin_color": "Blue",
    "bin": "Blue Plastic Bin"
  }],
  "limit": 20,
  "next_cursor": null
}
```

#### 3.4.2 Log New Scan Record
* **Endpoint:** `POST /api/history`, JSON body, **201 Created**.
* Required: `user_id` (device UUID), `item_name`, canonical `category`, and
  `confidence` in [0,1]. The server generates `scan_id` (UUID) and UTC `timestamp`
  if omitted, and derives `bin_color` and `bin`. Supplied timestamps must include
  a timezone; they are normalized to UTC.
* The response contains `status: "created"`, `scan_id`, and the complete `scan`.
  Resending the complete record with the same scan UUID replaces it without
  duplicating it. Stats/leaderboards are not modified by this endpoint.
* Invalid fields/limits: **422**; malformed or other-device cursor: **400**;
  configured Firestore unavailable: **503** without exposing database details.

See [the backend history guide](../backend/README.md#guest-scan-history) for
storage configuration and a three-record pagination example. Clients using the
old mock Bearer/offset contract must migrate to the device UUID/cursor contract.

---

### 3.5 User Profile & Gamification
* **Endpoint:** `GET /api/auth/me`
* **Description:** Retrieves the authenticated user's profile, eco-points, and current recycling streak.
* **Authentication:** Required (`Bearer <token>`)

#### Response (HTTP 200 OK)
```json
{
  "uid": "user_456",
  "email": "user@berkeley.edu",
  "display_name": "Janice Chen",
  "current_streak": 5,
  "total_scans": 28,
  "points": 280
}
```

---

## 4. Status Codes Summary

| Status Code | Description | Scenario |
|---|---|---|
| `200 OK` | Standard successful response | Successful GET or synchronous processing |
| `201 Created` | Resource successfully created | Successful record log |
| `400 Bad Request` | Invalid parameters or body | Validation failure or missing fields |
| `401 Unauthorized` | Missing or invalid auth token | Protected route accessed without credentials |
| `404 Not Found` | Resource not located | Unsupported city or scan record not found |
| `413 Payload Too Large` | Request entity too large | Uploaded image > 10MB |
| `415 Unsupported Media Type` | Media type rejected | Non-image file uploaded |
| `422 Unprocessable Entity` | Request validation failed | Missing file field or invalid guest UUID |
| `500 Internal Server Error` | Unhandled server exception | Unexpected server failure |
| `503 Service Unavailable` | Temporary capacity/storage failure | Busy inference workers or unavailable history store |
| `504 Gateway Timeout` | Inference deadline exceeded | Model execution took too long |

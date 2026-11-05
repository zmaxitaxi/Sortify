---
title: "feat(backend): Production Multi-Stage Dockerfile & Cloud Deployment"
labels: ["sprint-2", "backend", "devops"]
subteam: "backend"
deliverable_branch: "feat/backend/<claimant>/cloud-deployment"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-production-multi-stage-dockerfile--cloud-deployment"
---

## 🎯 Objective
Host the Sortify FastAPI backend on a publicly accessible HTTPS web service (Render or Google Cloud Run) so mobile devices can scan items from anywhere without localhost restrictions.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Production Multi-Stage Dockerfile & Cloud Deployment](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-production-multi-stage-dockerfile--cloud-deployment)
- **Backend Subteam Plan:** [Backend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_backend.md#ticket-production-multi-stage-dockerfile--cloud-deployment)
- **Starter Code Reference:** [starter_code/updated_backend_code.md#ticket-production-dockerfile](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_backend_code.md#ticket-production-dockerfile)

## 📁 Expected Files
- `backend/Dockerfile`
- `.dockerignore`
- `backend/DEPLOYMENT.md` (deployment configuration and environment variable setup)

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/backend/<claimant>/cloud-deployment`
- **Multi-Stage Dockerfile (`backend/Dockerfile`):**
  - Implement a two-stage build:
    1. `builder` stage: installs build tools (`gcc`, `libpq-dev`), builds Python dependencies from `requirements.txt` into `/root/.local`.
    2. `runner` stage: based on slim Python image (`python:3.11-slim`), copies installed dependencies and backend application code, strips compiler caches.
  - Configures dynamic port binding: `ENV PORT=8000`, `EXPOSE 8000`, executing `uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}`.
- **Docker Ignore (`.dockerignore`):**
  - Exclude `.git`, `.venv`, `__pycache__`, `.pytest_cache`, and temporary files from the build context.
- **Continuous Deployment & Verification:**
  - Connect repository `main` branch to Render Web Service or Google Cloud Run.
  - Set production environment variables: `PORT=8000`, `PROJECT_NAME="Sortify API"`, allowed CORS origins.
  - Verify live public URL: send a `curl` request to `https://<your-service-url>/health` and assert HTTP 200 `{"status": "ok"}`.

---

## 💻 Starter Scaffold

### `backend/Dockerfile`
```dockerfile
# ==========================================
# Stage 1: Build dependencies
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install minimal OS dependencies for building binary wheels if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==========================================
# Stage 2: Production runtime image
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy installed Python dependencies from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source
COPY backend /app/backend

# Configure dynamic port binding (Render/Cloud Run inject $PORT)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
```

### `.dockerignore`
```dockerignore
.git
.github
.venv
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.coverage
htmlcov/
data/raw/
data/raw_expanded/
ml/models/*.pth
!ml/models/sortify_mvp_v1.pth
node_modules/
.expo/
```

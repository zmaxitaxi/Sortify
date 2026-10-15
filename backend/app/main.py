"""FastAPI Main Application for Sortify."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.routers import auth, classify, history, rules, uploads

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Sortify Waste Sorting & Classification Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for Expo dev servers, mobile test devices, and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Week 1 learning route stays at /upload-image, outside the /api prefix.
app.include_router(uploads.router, tags=["Uploads"])

# Mount domain-specific API routers under /api
app.include_router(classify.router, prefix="/api", tags=["Classification"])
app.include_router(rules.router, prefix="/api", tags=["Rules"])
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(history.router, prefix="/api", tags=["History"])


@app.get("/health")
def health_check():
    """Service health check endpoint confirming server availability."""
    return {"status": "ok"}

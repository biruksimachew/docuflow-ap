from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.documents import (
    router as documents_router,
)
from app.api.routes.extractions import (
    router as extractions_router,
)
from app.api.routes.health import (
    router as health_router,
)
from app.core.config import settings
from app.db.database import engine


@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    description=(
        "Invoice intake, preprocessing, OCR, "
        "canonical extraction, deterministic validation, "
        "matching, human review and export API."
    ),
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.include_router(
    health_router
)

app.include_router(
    documents_router,
    prefix="/api/v1",
)

app.include_router(
    extractions_router,
    prefix="/api/v1",
)


@app.get(
    "/",
    tags=["Application"],
)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "readiness": "/health/ready",
        "invoice_upload": (
            "/api/v1/documents/upload"
        ),
        "processing_snapshot": (
            "/api/v1/documents/{document_id}/processing"
        ),
        "extraction_snapshot": (
            "/api/v1/documents/{document_id}/extraction"
        ),
    }
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import (
    router as auth_router,
)
from app.api.routes.decisions import (
    router as decisions_router,
)
from app.api.routes.documents import (
    router as documents_router,
)
from app.api.routes.duplicates import (
    router as duplicates_router,
)
from app.api.routes.extractions import (
    router as extractions_router,
)
from app.api.routes.health import (
    router as health_router,
)
from app.api.routes.line_items import (
    router as line_items_router,
)
from app.api.routes.matching import (
    router as matching_router,
)
from app.api.routes.reviews import (
    router as reviews_router,
)
from app.api.routes.validations import (
    router as validations_router,
)
from app.core.config import settings
from app.db.database import engine
from app.security.middleware import (
    DocumentSecurityMiddleware,
)


@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.13.0",
    description=(
        "Authenticated invoice intake, OCR, extraction, "
        "validation, duplicate detection, vendor and PO "
        "matching, authoritative decisions and human review."
    ),
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    DocumentSecurityMiddleware
)

app.include_router(
    health_router
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    documents_router,
    prefix="/api/v1",
)

app.include_router(
    decisions_router,
    prefix="/api/v1",
)

app.include_router(
    duplicates_router,
    prefix="/api/v1",
)

app.include_router(
    extractions_router,
    prefix="/api/v1",
)

app.include_router(
    line_items_router,
    prefix="/api/v1",
)

app.include_router(
    matching_router,
    prefix="/api/v1",
)

app.include_router(
    reviews_router,
    prefix="/api/v1",
)

app.include_router(
    validations_router,
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
        "authentication_profile": (
            "/api/v1/auth/me"
        ),
        "invoice_upload": (
            "/api/v1/documents/upload"
        ),
        "processing_snapshot": (
            "/api/v1/documents/{document_id}/processing"
        ),
        "extraction_snapshot": (
            "/api/v1/documents/{document_id}/extraction"
        ),
        "line_item_snapshot": (
            "/api/v1/documents/{document_id}/line-items"
        ),
        "validation_snapshot": (
            "/api/v1/documents/{document_id}/validation"
        ),
        "duplicate_snapshot": (
            "/api/v1/documents/{document_id}/duplicate-check"
        ),
        "matching_snapshot": (
            "/api/v1/documents/{document_id}/matching"
        ),
        "decision_snapshot": (
            "/api/v1/documents/{document_id}/decision"
        ),
        "review_queue": (
            "/api/v1/reviews"
        ),
    }
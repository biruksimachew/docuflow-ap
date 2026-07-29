from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings
from app.db.database import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Invoice OCR, deterministic validation, matching, "
        "human review and export API."
    ),
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/", tags=["Application"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "readiness": "/health/ready",
    }

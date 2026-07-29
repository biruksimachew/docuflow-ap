from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.core.config import settings
from app.db.database import check_database


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic liveness endpoint that does not depend on external services."""

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Check dependencies required for normal application operation."""

    database_ok = False
    redis_ok = False
    errors: dict[str, str] = {}

    try:
        database_ok = await check_database()
    except Exception as exc:
        errors["database"] = type(exc).__name__

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    try:
        redis_ok = bool(await redis_client.ping())
    except Exception as exc:
        errors["redis"] = type(exc).__name__
    finally:
        await redis_client.aclose()

    ready = database_ok and redis_ok

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": settings.app_name,
            "dependencies": {
                "database": database_ok,
                "redis": redis_ok,
            },
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

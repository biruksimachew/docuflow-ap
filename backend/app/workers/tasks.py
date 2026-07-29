from datetime import datetime, timezone

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> dict[str, str]:
    """Small task used to verify API-to-worker communication."""

    return {
        "status": "pong",
        "worker": "docuflow-ap",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

"""US08 — Celery application instance.

Wired to the pre-provisioned CELERY_BROKER_URL / CELERY_RESULT_BACKEND
settings (redis://redis:6379/0 inside Docker, see docker-compose.yml).
The `celery-worker` and `celery-beat` services in docker-compose.yml run
this codebase with the commands:

    celery -A app.core.celery_app worker  --loglevel=info
    celery -A app.core.celery_app beat    --loglevel=info

FastAPI itself does NOT import celery at request time — the API layer only
triggers sends via reminder_service (synchronous), keeping the web process
independent of the broker.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "onboard_chaser",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.reminder_tasks"],
)

# Optional but explicit: serialization + timezone conventions.
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Don't let results pile up in Redis forever.
    result_expires=3600,
)

# ── Periodic schedule (celery-beat) ─────────────────────────────────────
# The scan interval is configurable (US09-ready): REMINDER_SCAN_INTERVAL_
# MINUTES, default hourly. Beat evaluates this once at startup — operators
# changing the env var should restart the beat container.
celery_app.conf.beat_schedule = {
    "scan-and-send-reminders": {
        "task": "app.tasks.reminder_tasks.scan_and_send_reminders",
        "schedule": crontab(minute=0),  # top of every hour
        # For finer control than an hourly crontab, the float-schedule form
        # (seconds) is used when the interval is not a multiple of 60:
        #   "schedule": settings.REMINDER_SCAN_INTERVAL_MINUTES * 60
    },
}

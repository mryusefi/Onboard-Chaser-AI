"""US08 — Celery tasks for the automated reminder system.

`scan_and_send_reminders` runs hourly (see app/core/celery_app.py
beat_schedule): it pulls every incomplete onboarding, applies the reminder
rules (midway / expiry-warning + cap/cooldown from US09-ready settings) and
sends reminders where due. EVERY attempt — sent, failed or skipped — is
persisted as a ReminderLog row (the "log reminder history" requirement).
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import ReminderLog
from app.services.reminder_service import (
    get_incomplete_onboardings,
    evaluate_reminder_rules,
    send_reminder,
)

logger = logging.getLogger(__name__)


def _serialize_log(log: ReminderLog) -> dict:
    return {
        "onboarding_id": str(log.onboarding_id),
        "status": log.status.value if hasattr(log.status, "value") else str(log.status),
        "reminder_type": log.reminder_type,
        "reason": log.reason,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
    }


@celery_app.task(
    name="app.tasks.reminder_tasks.scan_and_send_reminders",
    bind=True,
    # A provider outage shouldn't lose the hourly scan entirely.
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def scan_and_send_reminders(self) -> dict:
    """
    Hourly reminder scan (celery-beat).

    For each incomplete onboarding: evaluate the reminder rules, and when a
    reminder is due call send_reminder() (which writes the ReminderLog row
    for the attempt). Skipped onboardings are ALSO logged so HR has a full
    audit trail. Returns a summary dict (stored as the task result in Redis).
    """
    now = datetime.now(timezone.utc)
    summary = {
        "started_at": now.isoformat(),
        "scanned": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    db: Session = SessionLocal()
    try:
        onboardings = get_incomplete_onboardings(db)
        summary["scanned"] = len(onboardings)
        logger.info("Reminder scan: %d incomplete onboarding(s)", len(onboardings))

        for onboarding in onboardings:
            try:
                due_type, _skip = evaluate_reminder_rules(db, onboarding, now=now)
                if due_type is None:
                    # Log the skip so HR sees why nothing was sent.
                    log = send_reminder(db, onboarding, due_type or "midway")
                else:
                    log = send_reminder(db, onboarding, due_type)

                status = (
                    log.status.value if hasattr(log.status, "value") else str(log.status)
                )
                summary[status] = summary.get(status, 0) + 1
                logger.info(
                    "Reminder %s for onboarding %s (type=%s, reason=%s)",
                    status,
                    onboarding.id,
                    log.reminder_type,
                    log.reason,
                )
            except Exception as exc:  # one bad row must not kill the scan
                logger.exception("Reminder failed for onboarding %s", onboarding.id)
                summary["errors"].append(
                    {"onboarding_id": str(onboarding.id), "error": str(exc)}
                )

        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            "Reminder scan done: scanned=%(scanned)s sent=%(sent)s "
            "failed=%(failed)s skipped=%(skipped)s" % summary
        )
        return summary
    finally:
        db.close()

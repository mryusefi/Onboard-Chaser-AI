"""US08 — Automated reminder service.

Design notes
────────────
Reminder rules (documented per the US08 requirement):

  An onboarding is *incomplete* when its status is PENDING or IN_PROGRESS
  (i.e. not COMPLETED) AND it has at least one document not in
  UPLOADED/COMPLETED status. The anchor time is ``invitation_sent_at``
  (falling back to ``created_at`` when the invitation email has never been
  sent).

  Rule 1 — "midway": once >= REMINDER_MIDWAY_PERCENT (default 50%) of the
  token lifetime has elapsed since the anchor and before the halfway point
  of the *next* interval (so each halfway milestone fires at most once).
  No token lifetime (token_expires_at is None) -> no midway reminder; the
  midpoint math needs a finite lifetime.

  Rule 2 — "expiry_warning": when the time remaining until
  ``token_expires_at`` is within REMINDER_EXPIRY_WINDOW_HOURS (default 24h)
  of expiry. Complements rule 1; each halfway milestone fires at most once.

  Cap / cooldown (anti-spam, both part of US09 config):
    - REMINDER_COOLDOWN_HOURS (default 24): minimum interval between two
      reminders for the same onboarding (any type).
    - REMINDER_MAX_COUNT (default 3): maximum number of *successfully sent*
      reminders per onboarding; after that everything is skipped.

  All thresholds are read LIVE from ``app.core.config.settings`` at
  evaluation time so US09 can expose them in an admin config UI without any
  code change in this module; the Settings defaults above act as the safe
  fallback when no config exists yet.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Onboarding,
    OnboardingStatus,
    Document,
    DocumentStatus,
    ReminderLog,
    ReminderStatus,
)
from app.services.email_service import (
    is_email_configured,
    render_reminder_email,
    render_reminder_plain_text,
    _send_resend,
)

# ────────────────────────────────────────────────────────────────────────
# Reminder type constants (stored on ReminderLog.reminder_type)
# ────────────────────────────────────────────────────────────────────────
REMINDER_TYPE_MIDWAY = "midway"
REMINDER_TYPE_EXPIRY = "expiry_warning"


# ────────────────────────────────────────────────────────────────────────
# 1) Candidate selection — onboardings that still owe us documents
# ────────────────────────────────────────────────────────────────────────
def get_incomplete_onboardings(db: Session) -> list[Onboarding]:
    """
    Return onboardings that are pending/in_progress (NOT completed) and have
    at least one document not yet uploaded/completed.

    Ordered by the soonest token expiry so the scan works on the most
    urgent cases first.
    """
    return (
        db.query(Onboarding)
        .filter(Onboarding.status.in_([OnboardingStatus.PENDING, OnboardingStatus.IN_PROGRESS]))
        .filter(
            Onboarding.documents.any(
                Document.status.notin_([DocumentStatus.UPLOADED, DocumentStatus.COMPLETED])
            )
        )
        # Soonest-expiring links first (NULLs last: nothing to remind about).
        .order_by(Onboarding.token_expires_at.asc())
        .all()
    )


def _anchor_time(onboarding: Onboarding) -> datetime | None:
    """Invitation time, or creation time when no invitation was ever sent."""
    anchor = onboarding.invitation_sent_at or onboarding.created_at
    if anchor is None:
        return None
    # SQLite (tests) returns naive datetimes; normalize to UTC-aware.
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return anchor


def _expires_at(onboarding: Onboarding) -> datetime | None:
    expires = onboarding.token_expires_at
    if expires is None:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires


# ────────────────────────────────────────────────────────────────────────
# 2) Rule evaluation — which reminder (if any) is due right now?
# ───────────────────────────────────────────────────────────────────────
def _last_send_attempt(db: Session, onboarding_id: UUID) -> ReminderLog | None:
    """
    Most recent reminder that actually tried to send (SENT or FAILED).

    Skipped rows are audit-only: they must NOT start a cooldown, otherwise
    an hourly scan logging "no reminder due" would keep pushing the next
    eligible attempt a full cooldown window into the future.
    """
    return (
        db.query(ReminderLog)
        .filter(
            ReminderLog.onboarding_id == onboarding_id,
            ReminderLog.status.in_([ReminderStatus.SENT, ReminderStatus.FAILED]),
        )
        .order_by(ReminderLog.sent_at.desc())
        .first()
    )


def _sent_reminder_count(db: Session, onboarding_id: UUID) -> int:
    return (
        db.query(ReminderLog)
        .filter(
            ReminderLog.onboarding_id == onboarding_id,
            ReminderLog.status == ReminderStatus.SENT,
        )
        .count()
    )


def evaluate_reminder_rules(
    db: Session, onboarding: Onboarding, now: datetime | None = None
) -> tuple[str | None, str | None]:
    """
    Decide whether a reminder is due for ``onboarding`` right now.

    Returns:
        (reminder_type, skip_reason):
          reminder_type  -> REMINDER_TYPE_MIDWAY / REMINDER_TYPE_EXPIRY, or
                            None when nothing is due.
          skip_reason    -> None when a type is returned; otherwise a short
                            human-readable string (logged as ReminderLog
                            'skipped' reason by the caller).

    Thresholds are read live from settings (US09-ready, safe defaults).
    """
    if not settings.REMINDER_ENABLED:
        return None, "reminders disabled (REMINDER_ENABLED=false)"

    now = now or datetime.now(timezone.utc)
    anchor = _anchor_time(onboarding)
    expires = _expires_at(onboarding)

    # Cap: max successfully-sent reminders per onboarding.
    sent_count = _sent_reminder_count(db, onboarding.id)
    if sent_count >= settings.REMINDER_MAX_COUNT:
        return None, (
            f"reminder cap reached ({sent_count}/{settings.REMINDER_MAX_COUNT} sent)"
        )

    # Cooldown: minimum interval since the last SEND ATTEMPT of any kind
    # (sent or failed — a failed attempt also counts so provider outages
    # can't trigger a tight retry loop; audit-only skips don't count).
    last = _last_send_attempt(db, onboarding.id)
    if last is not None:
        last_at = last.sent_at
        if last_at is not None:
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            cooldown = timedelta(hours=settings.REMINDER_COOLDOWN_HOURS)
            elapsed = now - last_at
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                return None, (
                    f"cooldown active: last attempt "
                    f"{elapsed.total_seconds() / 3600:.1f}h ago "
                    f"(next in ~{remaining.total_seconds() / 3600:.1f}h)"
                )

    # Token must exist and still be live for any reminder to make sense.
    if expires is None or expires <= now:
        return None, "no active token (never sent, already regenerated, or expired)"

    if anchor is None:
        return None, "no anchor time (no invitation_sent_at and no created_at)"

    lifetime = expires - anchor
    if lifetime <= timedelta(0):
        return None, "non-positive token lifetime"

    elapsed = now - anchor

    # Rule 1 — midway reminder: 50% (configurable) of the lifetime elapsed,
    # and we are still inside that same interval (each halfway milestone
    # fires at most once; the expiry window picks the next one up).
    halfway = lifetime * settings.REMINDER_MIDWAY_PERCENT
    if elapsed >= halfway and elapsed < expires - anchor - halfway / 2:
        return REMINDER_TYPE_MIDWAY, None

    # Rule 2 — expiry warning: within the configured window before expiry.
    if (expires - now) <= timedelta(hours=settings.REMINDER_EXPIRY_WINDOW_HOURS):
        return REMINDER_TYPE_EXPIRY, None

    return None, "no reminder due (before halfway point, outside expiry window)"


# ────────────────────────────────────────────────────────────────────────
# 3) Reminder e-mail — reuses email_service's Resend integration
# ────────────────────────────────────────────────────────────────────────
def _missing_documents(onboarding: Onboarding) -> list[dict]:
    """Only the documents still owed: status pending or missing."""
    docs = onboarding.documents or []
    return [
        {
            "name": d.name,
            "instructions": d.instructions,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
        }
        for d in docs
        if d.status not in (DocumentStatus.UPLOADED, DocumentStatus.COMPLETED)
    ]


def send_reminder(
    db: Session,
    onboarding: Onboarding,
    reminder_type: str,
    *,
    force: bool = False,
) -> ReminderLog:
    """
    Render + send one reminder e-mail and WRITE A REMINDERLOG FOR EVERY
    ATTEMPT (US08: sent, failed or skipped).

    Parameters
    ----------
    db              : SQLAlchemy session (caller owns commit).
    onboarding      : target onboarding (candidate + documents are loaded).
    reminder_type   : REMINDER_TYPE_MIDWAY / REMINDER_TYPE_EXPIRY — stored on
                      the ReminderLog row for HR visibility.
    force           : when True (manual HR trigger) the cap and cooldown
                      checks are bypassed, but the ReminderLog row is still
                      written exactly like for scheduled attempts.

    Returns the persisted ReminderLog so callers can build API responses.
    """
    now = datetime.now(timezone.utc)

    # ── Rule evaluation (skippable via `force`) ─────────────────────────
    skip_reason: str | None = None
    if not force:
        due_type, skip_reason = evaluate_reminder_rules(db, onboarding, now=now)
        if due_type is None:
            reminder_type = reminder_type or REMINDER_TYPE_MIDWAY
            log = ReminderLog(
                onboarding_id=onboarding.id,
                sent_at=now,
                status=ReminderStatus.SKIPPED,
                reminder_type=reminder_type,
                reason=skip_reason or "reminder not due",
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return log
        # The rule engine's verdict wins over the caller's label so the
        # audit trail always reflects WHY the reminder fired.
        reminder_type = due_type

    candidate = onboarding.candidate
    token = onboarding.magic_token

    # Without a live magic link there is nothing useful to remind about.
    if not token or not candidate:
        log = ReminderLog(
            onboarding_id=onboarding.id,
            sent_at=now,
            status=ReminderStatus.SKIPPED,
            reminder_type=reminder_type,
            reason="no magic token or candidate for onboarding",
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    anchor = _anchor_time(onboarding)
    expires = _expires_at(onboarding)
    if expires is None:
        log = ReminderLog(
            onboarding_id=onboarding.id,
            sent_at=now,
            status=ReminderStatus.SKIPPED,
            reminder_type=reminder_type,
            reason="no token_expires_at set (cannot compute days remaining)",
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    days_left = max(0, (expires - now).days)
    portal_url = f"{settings.FRONTEND_URL}/onboard/{token}"
    missing_docs = _missing_documents(onboarding)

    html = render_reminder_email(
        candidate_name=candidate.full_name,
        company_name=settings.APP_NAME,
        position=candidate.position,
        portal_url=portal_url,
        days_left=days_left,
        docs=missing_docs,
    )
    text = render_reminder_plain_text(
        candidate_name=candidate.full_name,
        company_name=settings.APP_NAME,
        position=candidate.position,
        portal_url=portal_url,
        days_left=days_left,
        docs=missing_docs,
    )

    subject = (
        f"Reminder: {len(missing_docs)} document"
        f"{'' if len(missing_docs) == 1 else 's'} still pending "
        f"for your {settings.APP_NAME} onboarding"
    )

    # ── Graceful fallback — same pattern as US07: never crash ──────────
    if not is_email_configured():
        log = ReminderLog(
            onboarding_id=onboarding.id,
            sent_at=now,
            status=ReminderStatus.SKIPPED,
            reminder_type=reminder_type,
            reason="RESEND_API_KEY not configured (email service unavailable)",
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    try:
        _send_resend(
            to=candidate.email,
            subject=subject,
            html=html,
            text=text,
        )
        log = ReminderLog(
            onboarding_id=onboarding.id,
            sent_at=now,
            status=ReminderStatus.SENT,
            reminder_type=reminder_type,
            reason=None,
        )
    except Exception as exc:  # provider error -> recorded, not re-raised
        log = ReminderLog(
            onboarding_id=onboarding.id,
            sent_at=now,
            status=ReminderStatus.FAILED,
            reminder_type=reminder_type,
            reason=str(exc),
        )

    db.add(log)
    db.commit()
    db.refresh(log)
    return log

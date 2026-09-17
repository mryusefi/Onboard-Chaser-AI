"""US09 + maintenance pass — HR settings endpoints.

/reminders            : global reminder configuration (US09)
/email-status         : whether email sending is configured (Item 1)
/email-status/test    : send a test email to the logged-in HR user (Item 1)
/email-template       : HR-editable invitation email copy (Item 1b)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import ReminderConfigResponse, ReminderConfigUpdate
from app.services.reminder_service import get_reminder_config, apply_reminder_config

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/reminders", response_model=ReminderConfigResponse)
def get_reminder_settings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Current reminder configuration (US09).

    The singleton row is auto-created with defaults on first read, so this
    always returns a usable config even before HR ever saved one.
    """
    config = get_reminder_config(db)
    if config is None:  # pragma: no cover - get_reminder_config always returns
        raise HTTPException(status_code=500, detail="Could not load reminder configuration")
    return config


@router.put("/reminders", response_model=ReminderConfigResponse)
def update_reminder_settings(
    body: ReminderConfigUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update the reminder configuration (US09). HR-authenticated.

    Validation (see reminder_service.apply_reminder_config):
      - reminder_frequency_hours >= 1
      - first_reminder_after_hours >= 0
      - final_reminder_before_expiry_hours >= 1 and
        < MAGIC_TOKEN_EXPIRE_HOURS (must fire while the link is live)
      - max_reminders_per_onboarding >= 1

    Invalid values are rejected with 422 and the stored config is untouched.
    """
    updates = body.model_dump(exclude_unset=True)
    try:
        config = apply_reminder_config(db, updates)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return config


# ────────────────────────────────────────────────────────────────────────
# Maintenance pass Item 1 / 1b — email configuration status + template
# ────────────────────────────────────────────────────────────────────────
class EmailStatusResponse(BaseModel):
    """
    Email-sending configuration state. Booleans only — the API key value is
    NEVER returned to the frontend (it lives in server env, same rule as the
    R2 credentials).
    """
    resend_configured: bool
    email_from: str | None = None
    # human-readable hint shown in the UI when resend_configured is false
    setup_hint: str | None = None


class EmailTestResponse(BaseModel):
    """Result of the send-test-email action."""
    status: str                 # sent | failed | not_sent
    message: str
    sent_to: str | None = None


class EmailTemplateResponse(BaseModel):
    """HR-editable invitation email copy (singleton; defaults when unset)."""
    subject_template: str | None = None
    body_intro: str | None = None
    body_closing: str | None = None
    extra_instructions: str | None = None


class EmailTemplateUpdate(BaseModel):
    subject_template: str | None = None
    body_intro: str | None = None
    body_closing: str | None = None
    extra_instructions: str | None = None

    @field_validator("subject_template")
    @classmethod
    def _subject_len(cls, v):
        if v is not None and len(v) > 200:
            raise ValueError("subject_template must be 200 characters or fewer")
        return v

    @field_validator("body_intro", "body_closing", "extra_instructions")
    @classmethod
    def _text_len(cls, v):
        if v is not None and len(v) > 2000:
            raise ValueError("template text must be 2000 characters or fewer")
        return v


@router.get("/email-status", response_model=EmailStatusResponse)
def get_email_status(
    current_user=Depends(get_current_user),
):
    """
    Whether email sending is configured on THIS SERVER (Item 1).

    Booleans only; the API key value is never returned. Lets any HR user see
    at a glance that a 401/failed send is a deployment-configuration issue,
    not something wrong with their account.
    """
    from app.services.email_service import _email_config_state

    state = _email_config_state()
    configured = state["resend_configured"]
    from app.services.email_service import NOT_CONFIGURED_HINT
    return EmailStatusResponse(
        resend_configured=configured,
        email_from=state["email_from"] if configured else None,
        setup_hint=None if configured else NOT_CONFIGURED_HINT,
    )


@router.post("/email-status/test", response_model=EmailTestResponse)
def send_test_email(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a test invitation-style email to the LOGGED-IN HR user's own
    address (Item 1) — verifies the deployment's email setup without
    touching Swagger or the API panel.
    """
    from app.services.email_service import (
        is_email_configured,
        _send_resend,
        NOT_CONFIGURED_HINT,
    )
    from app.core.config import settings as app_settings

    to = current_user.email
    if not is_email_configured():
        return EmailTestResponse(status="not_sent", message=NOT_CONFIGURED_HINT)

    try:
        _send_resend(
            to=to,
            subject=f"[{app_settings.APP_NAME}] Test email — your email setup works",
            html=(
                f"<p>Hi {current_user.full_name or 'there'},</p>"
                "<p>This is a test email from Onboard Chaser AI. If you're reading "
                "this in your inbox, email sending is configured correctly and "
                "candidate invitations will be delivered.</p>"
            ),
            text=(
                f"Hi {current_user.full_name or 'there'}, — this is a test email "
                "from Onboard Chaser AI. Email sending works."
            ),
        )
        return EmailTestResponse(
            status="sent", message="Test email sent — check your inbox.", sent_to=to
        )
    except Exception as exc:
        return EmailTestResponse(status="failed", message=str(exc), sent_to=to)


@router.get("/email-template", response_model=EmailTemplateResponse)
def get_email_template(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    HR-editable invitation email copy (Item 1b). Returns the stored row's
    fields, or nulls when never customized (the built-in template applies).
    """
    from app.services.email_service import _load_template_config

    cfg = _load_template_config(db) or {}
    return EmailTemplateResponse(**cfg)


@router.put("/email-template", response_model=EmailTemplateResponse)
def update_email_template(
    body: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update the HR-editable invitation copy (Item 1b). Only the copy is
    editable — the portal link, document list and expiry notice are always
    injected by email_service.py, and the RESEND_API_KEY stays in env.
    """
    from app.models.models import EmailTemplateConfig

    row = db.query(EmailTemplateConfig).filter(EmailTemplateConfig.id == 1).first()
    if not row:
        row = EmailTemplateConfig(id=1)
        db.add(row)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return EmailTemplateResponse(
        subject_template=row.subject_template,
        body_intro=row.body_intro,
        body_closing=row.body_closing,
        extra_instructions=row.extra_instructions,
    )

"""US09 — HR settings endpoints for the global reminder configuration."""
from fastapi import APIRouter, Depends, HTTPException
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

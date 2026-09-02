"""Tests for US09 — Reminder configuration (singleton ReminderConfig row)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, pwd_context
from app.core.config import settings
from app.models.models import (
    Candidate,
    Onboarding,
    Document,
    ReminderConfig,
    ReminderLog,
    ReminderStatus,
    OnboardingStatus,
    DocumentStatus,
    User,
)
from tests.conftest import TestingSession

client = TestClient(app)

# Built-in defaults match the model column defaults / config.py env defaults.
DEFAULTS = {
    "reminder_frequency_hours": 24,
    "first_reminder_after_hours": 24,
    "final_reminder_before_expiry_hours": 24,
    "max_reminders_per_onboarding": 3,
    "is_enabled": True,
}


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


def _make_onboarding(
    db, hr_user, *, invited_hours_ago=41.0, expires_in_hours=39.0,
    status=OnboardingStatus.IN_PROGRESS,
):
    """Onboarding + one pending doc; default anchor puts it inside the
    midway window of the 80h lifetime (41h elapsed > 24h first-delay)."""
    cand = Candidate(
        email=f"cand_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Config Test",
        created_by=hr_user.id,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    now = datetime.now(timezone.utc)
    onb = Onboarding(
        candidate_id=cand.id,
        status=status,
        magic_token="tok-" + uuid.uuid4().hex[:8],
        invitation_sent_at=now - timedelta(hours=invited_hours_ago),
        token_expires_at=now + timedelta(hours=expires_in_hours),
    )
    db.add(onb)
    db.commit()
    db.refresh(onb)
    db.add(Document(onboarding_id=onb.id, name="Government ID", status=DocumentStatus.PENDING))
    db.commit()
    return onb


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"hr9_{uuid.uuid4().hex[:6]}@test.com",
        full_name="HR Nine",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ────────────────────────────────────────────────────────────────────────
# GET /api/v1/settings/reminders
# ────────────────────────────────────────────────────────────────────────
class TestGetReminderSettings:
    def test_returns_default_config_when_none_exists(self, db, hr_user):
        # No ReminderConfig row has been created by this test run.
        resp = client.get("/api/v1/settings/reminders", headers=_headers_for(hr_user))
        assert resp.status_code == 200
        data = resp.json()
        for field, expected in DEFAULTS.items():
            assert data[field] == expected, field
        # Auto-created: the row now exists in the DB.
        row = db.query(ReminderConfig).filter(ReminderConfig.id == 1).first()
        assert row is not None

    def test_get_is_idempotent_single_row(self, db, hr_user):
        for _ in range(3):
            r = client.get("/api/v1/settings/reminders", headers=_headers_for(hr_user))
            assert r.status_code == 200
        assert db.query(ReminderConfig).count() == 1

    def test_get_requires_auth(self, db, hr_user):
        resp = client.get("/api/v1/settings/reminders")
        assert resp.status_code == 401


# ────────────────────────────────────────────────────────────────────────
# PUT /api/v1/settings/reminders — happy paths
# ────────────────────────────────────────────────────────────────────────
class TestUpdateReminderSettings:
    def test_put_updates_all_fields(self, db, hr_user):
        payload = {
            "reminder_frequency_hours": 12,
            "first_reminder_after_hours": 6,
            "final_reminder_before_expiry_hours": 10,
            "max_reminders_per_onboarding": 5,
            "is_enabled": False,
        }
        resp = client.put("/api/v1/settings/reminders", json=payload,
                          headers=_headers_for(hr_user))
        assert resp.status_code == 200
        data = resp.json()
        for field, expected in payload.items():
            assert data[field] == expected, field
        row = db.query(ReminderConfig).filter(ReminderConfig.id == 1).first()
        assert row.reminder_frequency_hours == 12
        assert row.is_enabled is False

    def test_put_persists_across_reads(self, db, hr_user):
        resp = client.put(
            "/api/v1/settings/reminders",
            json={"reminder_frequency_hours": 48},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        # Fresh session sees the persisted change (integration-style).
        fresh = TestingSession()
        try:
            row = fresh.query(ReminderConfig).filter(ReminderConfig.id == 1).first()
            assert row.reminder_frequency_hours == 48
        finally:
            fresh.close()

    def test_put_requires_auth(self, db, hr_user):
        resp = client.put("/api/v1/settings/reminders", json={"is_enabled": False})
        assert resp.status_code == 401


# ────────────────────────────────────────────────────────────────────────
# PUT validation — invalid values rejected, config untouched
# ────────────────────────────────────────────────────────────────────────
class TestUpdateReminderSettingsValidation:
    def test_negative_frequency_rejected(self, db, hr_user):
        resp = client.put("/api/v1/settings/reminders",
                          json={"reminder_frequency_hours": -1},
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422
        assert "reminder_frequency_hours" in resp.json()["detail"]

    def test_zero_frequency_rejected(self, db, hr_user):
        resp = client.put("/api/v1/settings/reminders",
                          json={"reminder_frequency_hours": 0},
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422

    def test_max_reminders_below_one_rejected(self, db, hr_user):
        resp = client.put("/api/v1/settings/reminders",
                          json={"max_reminders_per_onboarding": 0},
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422
        assert "max_reminders_per_onboarding" in resp.json()["detail"]

    def test_final_reminder_at_or_above_token_lifetime_rejected(self, db, hr_user):
        # MAGIC_TOKEN_EXPIRE_HOURS = 72 -> final window must be < 72.
        for value in (72, 96):
            resp = client.put("/api/v1/settings/reminders",
                              json={"final_reminder_before_expiry_hours": value},
                              headers=_headers_for(hr_user))
            assert resp.status_code == 422, value
            assert "MAGIC_TOKEN_EXPIRE_HOURS" in resp.json()["detail"]

    def test_negative_first_delay_rejected(self, db, hr_user):
        resp = client.put("/api/v1/settings/reminders",
                          json={"first_reminder_after_hours": -5},
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422
        assert "first_reminder_after_hours" in resp.json()["detail"]

    def test_invalid_put_leaves_config_untouched(self, db, hr_user):
        # Seed a known-good config, then attempt an invalid update.
        client.put("/api/v1/settings/reminders",
                   json={"reminder_frequency_hours": 36},
                   headers=_headers_for(hr_user))
        resp = client.put("/api/v1/settings/reminders",
                          json={"reminder_frequency_hours": 0},
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422
        row = db.query(ReminderConfig).filter(ReminderConfig.id == 1).first()
        assert row.reminder_frequency_hours == 36  # unchanged


# ────────────────────────────────────────────────────────────────────────
# Integration — reminder_service picks up updated config values
# ────────────────────────────────────────────────────────────────────────
class TestServiceUsesLiveConfig:
    def test_updated_frequency_applies_to_cooldown(self, db, hr_user):
        # Tighten the frequency to 2h, then send; a 1h-old attempt must now
        # still block (2h cooldown) — with the old 24h default the skip
        # reason window differs, proving the live value is used either way.
        client.put("/api/v1/settings/reminders",
                   json={"reminder_frequency_hours": 2},
                   headers=_headers_for(hr_user))
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "cooldown" in reason

    def test_disable_via_config_stops_reminders(self, db, hr_user):
        # HR flips the kill switch off through the API (not monkeypatch).
        client.put("/api/v1/settings/reminders",
                   json={"is_enabled": False},
                   headers=_headers_for(hr_user))
        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "disabled" in reason

    def test_reenable_via_config_resumes_reminders(self, db, hr_user):
        client.put("/api/v1/settings/reminders",
                   json={"is_enabled": False},
                   headers=_headers_for(hr_user))
        client.put("/api/v1/settings/reminders",
                   json={"is_enabled": True},
                   headers=_headers_for(hr_user))
        onb = _make_onboarding(db, hr_user)  # 41h elapsed -> past first delay
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype == "midway"
        assert reason is None

    def test_first_reminder_delay_gate_from_config(self, db, hr_user):
        # Raise the quiet period to 50h: an onboarding invited 41h ago must
        # now be skipped even though it is past the midway point.
        client.put("/api/v1/settings/reminders",
                   json={"first_reminder_after_hours": 50},
                   headers=_headers_for(hr_user))
        onb = _make_onboarding(db, hr_user, invited_hours_ago=41.0,
                               expires_in_hours=39.0)
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "first-reminder delay" in reason

    def test_send_reminder_honors_disabled_config(self, db, hr_user, monkeypatch):
        client.put("/api/v1/settings/reminders",
                   json={"is_enabled": False},
                   headers=_headers_for(hr_user))
        onb = _make_onboarding(db, hr_user)
        mock_send = MagicMock()
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)
        from app.services.reminder_service import send_reminder

        log = send_reminder(db, onb, "midway")
        assert log.status == ReminderStatus.SKIPPED
        assert "disabled" in log.reason
        mock_send.assert_not_called()

"""Tests for US08 — Automated Reminder System (Celery + ReminderLog)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, pwd_context
from app.core.config import settings
from app.models.models import (
    User,
    Candidate,
    Onboarding,
    Document,
    ReminderLog,
    ReminderStatus,
    OnboardingStatus,
    DocumentStatus,
)
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


def _make_onboarding(
    db, hr_user, *, status=OnboardingStatus.IN_PROGRESS, doc_status=DocumentStatus.PENDING,
    invited_hours_ago=41.0, expires_in_hours=39.0, token="tok-" + uuid.uuid4().hex[:8],
):
    """Build candidate + onboarding + one pending document, anchored so the
    midway rule fires (default): invited 41h ago, link expires in 39h."""
    cand = Candidate(
        email=f"cand_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Remind Me",
        created_by=hr_user.id,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    now = datetime.now(timezone.utc)
    onb = Onboarding(
        candidate_id=cand.id,
        status=status,
        magic_token=token,
        invitation_sent_at=now - timedelta(hours=invited_hours_ago),
        token_expires_at=now + timedelta(hours=expires_in_hours),
    )
    db.add(onb)
    db.commit()
    db.refresh(onb)

    doc = Document(
        onboarding_id=onb.id,
        name="Government ID",
        status=doc_status,
    )
    db.add(doc)
    db.commit()
    return onb


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"hr8_{uuid.uuid4().hex[:6]}@test.com",
        full_name="HR Eight",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ────────────────────────────────────────────────────────────────────────
# Reminder service — candidate selection + rule engine
# ────────────────────────────────────────────────────────────────────────
class TestGetIncompleteOnboardings:
    def test_returns_incomplete_with_pending_doc(self, db, hr_user):
        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import get_incomplete_onboardings

        ids = [o.id for o in get_incomplete_onboardings(db)]
        assert onb.id in ids

    def test_excludes_completed(self, db, hr_user):
        onb = _make_onboarding(db, hr_user, status=OnboardingStatus.COMPLETED)
        from app.services.reminder_service import get_incomplete_onboardings

        assert onb.id not in [o.id for o in get_incomplete_onboardings(db)]

    def test_excludes_all_documents_uploaded(self, db, hr_user):
        onb = _make_onboarding(db, hr_user, doc_status=DocumentStatus.UPLOADED)
        from app.services.reminder_service import get_incomplete_onboardings

        assert onb.id not in [o.id for o in get_incomplete_onboardings(db)]

    def test_includes_missing_document(self, db, hr_user):
        onb = _make_onboarding(db, hr_user, doc_status=DocumentStatus.MISSING)
        from app.services.reminder_service import get_incomplete_onboardings

        assert onb.id in [o.id for o in get_incomplete_onboardings(db)]


class TestReminderRules:
    def test_midway_fires_at_half_lifetime(self, db, hr_user):
        onb = _make_onboarding(db, hr_user)  # 41h elapsed of 80h → midway due
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype == "midway"
        assert reason is None

    def test_no_reminder_before_halfway(self, db, hr_user):
        onb = _make_onboarding(
            db, hr_user, invited_hours_ago=10.0, expires_in_hours=70.0
        )
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "no reminder due" in reason

    def test_expiry_warning_within_window(self, db, hr_user):
        # Invited 79h ago of 80h → past halfway AND 1h left (< 24h window).
        onb = _make_onboarding(
            db, hr_user, invited_hours_ago=79.0, expires_in_hours=1.0
        )
        from app.services.reminder_service import (
            evaluate_reminder_rules,
            REMINDER_TYPE_EXPIRY,
        )

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype == REMINDER_TYPE_EXPIRY
        assert reason is None

    def test_disabled_master_switch_skips(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(settings, "REMINDER_ENABLED", False)
        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "disabled" in reason

    def test_cap_reached_skips(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(settings, "REMINDER_MAX_COUNT", 2)
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=30),
        ))
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="expiry_warning", sent_at=datetime.now(timezone.utc) - timedelta(hours=5),
        ))
        db.commit()
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "cap" in reason

    def test_cooldown_active_skips(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(settings, "REMINDER_COOLDOWN_HOURS", 24)
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ))
        db.commit()
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "cooldown" in reason

    def test_failed_attempt_respects_cooldown_too(self, db, hr_user):
        # Even a failed attempt starts a cooldown — no tight retry loop.
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.FAILED,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "cooldown" in reason

    def test_expired_token_skips(self, db, hr_user):
        onb = _make_onboarding(
            db, hr_user, invited_hours_ago=100.0, expires_in_hours=-20.0
        )
        from app.services.reminder_service import evaluate_reminder_rules

        rtype, reason = evaluate_reminder_rules(db, onb)
        assert rtype is None
        assert "expired" in reason or "no active token" in reason


# ────────────────────────────────────────────────────────────────────────
# send_reminder — send / fail / skip logging
# ────────────────────────────────────────────────────────────────────────
class TestSendReminder:
    def test_sends_and_logs(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        mock_send = MagicMock()
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)

        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import send_reminder, REMINDER_TYPE_MIDWAY

        log = send_reminder(db, onb, REMINDER_TYPE_MIDWAY)
        assert log.status == ReminderStatus.SENT
        assert log.reminder_type == "midway"
        assert log.onboarding_id == onb.id
        mock_send.assert_called_once()
        # Only the missing doc is listed in the payload
        kwargs = mock_send.call_args.kwargs
        assert "Government ID" in kwargs["html"]
        assert "1 document" in kwargs["subject"]

    def test_no_resend_key_skips_without_crash(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: False
        )
        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import send_reminder

        log = send_reminder(db, onb, "midway")
        assert log.status == ReminderStatus.SKIPPED
        assert "RESEND_API_KEY" in log.reason

    def test_provider_failure_logged_as_failed(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        monkeypatch.setattr(
            "app.services.reminder_service._send_resend",
            MagicMock(side_effect=Exception("rate limit")),
        )
        onb = _make_onboarding(db, hr_user)
        from app.services.reminder_service import send_reminder

        log = send_reminder(db, onb, "expiry_warning")
        assert log.status == ReminderStatus.FAILED
        assert "rate limit" in log.reason

    def test_reminder_lists_only_missing_docs(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        mock_send = MagicMock()
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)

        onb = _make_onboarding(db, hr_user)
        # Second document already uploaded → only "Government ID" is listed.
        db.add(Document(onboarding_id=onb.id, name="Tax Form (W-4)",
                        status=DocumentStatus.UPLOADED))
        db.commit()
        from app.services.reminder_service import send_reminder

        send_reminder(db, onb, "midway")
        kwargs = mock_send.call_args.kwargs
        assert "Government ID" in kwargs["html"]
        assert "Tax Form (W-4)" not in kwargs["html"]

    def test_force_bypasses_cooldown(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        monkeypatch.setattr(
            "app.services.reminder_service._send_resend", MagicMock()
        )
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
        from app.services.reminder_service import send_reminder

        log = send_reminder(db, onb, "midway", force=True)
        assert log.status == ReminderStatus.SENT  # sent despite cooldown


# ────────────────────────────────────────────────────────────────────────
# HR endpoints — reminder history + manual trigger
# ────────────────────────────────────────────────────────────────────────
class TestReminderEndpoints:
    def test_reminder_history_requires_auth(self, db, hr_user):
        onb = _make_onboarding(db, hr_user)
        resp = client.get(f"/api/v1/onboarding/{onb.id}/reminders")
        assert resp.status_code == 401

    def test_reminder_history_empty_then_populated(self, db, hr_user, monkeypatch):
        onb = _make_onboarding(db, hr_user)
        headers = _headers_for(hr_user)

        resp = client.get(f"/api/v1/onboarding/{onb.id}/reminders", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        monkeypatch.setattr(
            "app.services.reminder_service._send_resend", MagicMock()
        )
        client.post(f"/api/v1/onboarding/{onb.id}/send-reminder-now", headers=headers)

        resp = client.get(f"/api/v1/onboarding/{onb.id}/reminders", headers=headers)
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 1
        assert history[0]["status"] == "sent"
        assert history[0]["reminder_type"] == "midway"
        assert history[0]["onboarding_id"] == str(onb.id)

    def test_reminder_history_404_unknown_id(self, db, hr_user):
        resp = client.get(
            "/api/v1/onboarding/00000000-0000-0000-0000-000000000000/reminders",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404

    def test_reminder_history_400_bad_uuid(self, db, hr_user):
        resp = client.get(
            "/api/v1/onboarding/not-a-uuid/reminders", headers=_headers_for(hr_user)
        )
        assert resp.status_code == 400

    def test_send_reminder_now_no_key_returns_skipped(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: False
        )
        onb = _make_onboarding(db, hr_user)
        headers = _headers_for(hr_user)
        resp = client.post(f"/api/v1/onboarding/{onb.id}/send-reminder-now", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert "RESEND_API_KEY" in data["reason"]
        assert data["candidate_email"] == onb.candidate.email
        # Attempt is audited even when skipped
        logs = db.query(ReminderLog).filter(ReminderLog.onboarding_id == onb.id).all()
        assert len(logs) == 1

    def test_send_reminder_now_success(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        mock_send = MagicMock()
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)
        onb = _make_onboarding(db, hr_user)
        resp = client.post(
            f"/api/v1/onboarding/{onb.id}/send-reminder-now",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["sent_at"] is not None
        mock_send.assert_called_once()

    def test_send_reminder_now_requires_auth(self, db, hr_user):
        onb = _make_onboarding(db, hr_user)
        resp = client.post(f"/api/v1/onboarding/{onb.id}/send-reminder-now")
        assert resp.status_code == 401

    def test_send_reminder_now_404_unknown(self, db, hr_user):
        resp = client.post(
            "/api/v1/onboarding/00000000-0000-0000-0000-000000000000/send-reminder-now",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────────
# Celery wiring — task, beat schedule, end-to-end scan
# ────────────────────────────────────────────────────────────────────────
class TestCeleryWiring:
    def test_beat_schedule_registered(self):
        from app.core.celery_app import celery_app

        assert "scan-and-send-reminders" in celery_app.conf.beat_schedule

    def test_task_registered_on_app(self):
        # Mirror worker startup: importing the tasks module registers the
        # @task against celery_app (via the include=["app.tasks..."] list).
        import app.tasks.reminder_tasks  # noqa: F401
        from app.core.celery_app import celery_app

        assert "app.tasks.reminder_tasks.scan_and_send_reminders" in celery_app.tasks

    def test_scan_task_end_to_end(self, db, hr_user, monkeypatch):
        """The hourly scan picks the due onboarding, sends, and logs it."""
        onb = _make_onboarding(db, hr_user)
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        mock_send = MagicMock()
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)
        # Point the task's session factory at the test (in-memory SQLite) DB.
        monkeypatch.setattr("app.tasks.reminder_tasks._session_factory", lambda: db)

        from app.tasks.reminder_tasks import scan_and_send_reminders

        summary = scan_and_send_reminders.run()
        assert summary["scanned"] >= 1
        assert summary["sent"] >= 1
        mock_send.assert_called_once()

        logs = db.query(ReminderLog).filter(ReminderLog.onboarding_id == onb.id).all()
        assert len(logs) == 1
        assert logs[0].status == ReminderStatus.SENT

    def test_scan_task_cooldown_skips_and_logs(self, db, hr_user, monkeypatch):
        onb = _make_onboarding(db, hr_user)
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SENT,
            reminder_type="midway", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
        monkeypatch.setattr(
            "app.services.reminder_service.is_email_configured", lambda: True
        )
        mock_send = MagicMock()
        monkeypatch.setattr("app.services.reminder_service._send_resend", mock_send)
        monkeypatch.setattr("app.tasks.reminder_tasks._session_factory", lambda: db)

        from app.tasks.reminder_tasks import scan_and_send_reminders

        summary = scan_and_send_reminders.run()
        assert summary["skipped"] >= 1
        mock_send.assert_not_called()
        # The skip is part of the audit trail
        logs = (
            db.query(ReminderLog)
            .filter(ReminderLog.onboarding_id == onb.id)
            .order_by(ReminderLog.sent_at.asc())
            .all()
        )
        assert logs[-1].status == ReminderStatus.SKIPPED
        assert "cooldown" in logs[-1].reason

    def test_scan_task_disabled_reminders(self, db, hr_user, monkeypatch):
        monkeypatch.setattr(settings, "REMINDER_ENABLED", False)
        _make_onboarding(db, hr_user)
        monkeypatch.setattr("app.tasks.reminder_tasks._session_factory", lambda: db)

        from app.tasks.reminder_tasks import scan_and_send_reminders

        summary = scan_and_send_reminders.run()
        assert summary["skipped"] >= 1
        assert summary["sent"] == 0

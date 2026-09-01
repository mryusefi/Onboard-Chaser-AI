"""Tests for US07 — Invitation Email."""
import os, sys, json, subprocess, uuid

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token, pwd_context
from app.models.models import User, Candidate, Onboarding, Document, InvitationEmailStatus
from tests.conftest import TestingSession

client = TestClient(app)


@pytest.fixture
def hr_user(db):
    user = User(
        email="hr7@test.com",
        full_name="HR Seven",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(hr_user):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(hr_user.id), 'email': hr_user.email})}"}


@pytest.fixture
def onboarding_with_candidate(db, hr_user):
    cand = Candidate(email="user@test.com", full_name="Test User", created_by=hr_user.id)
    db.add(cand)
    db.commit()
    db.refresh(cand)
    onb = Onboarding(candidate_id=cand.id, status="pending")
    db.add(onb)
    db.commit()
    db.refresh(onb)
    return onb


def _headers_for(user):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"}


# ─── Test: send invitation with valid Resend key ──────────────────────
def test_send_invitation_with_key(hr_user, auth_headers, onboarding_with_candidate):
    """Successful send updates status to 'sent' and records sent_at."""
    onboarding = onboarding_with_candidate
    with patch("app.services.email_service.is_email_configured", return_value=True):
        with patch("app.services.email_service._send_resend") as mock_send:
            mock_send.return_value = MagicMock(id="msg-123", status="sent")
            result = client.post(
                f"/api/v1/onboarding/{onboarding.id}/send-invitation",
                headers=auth_headers,
            )
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "sent"
    assert data["sent_at"] is not None
    assert data["portal_url"] is not None
    assert data["expiry_hours"] == 72  # from MAGIC_TOKEN_EXPIRE_HOURS
    # DB fields updated
    db_refresh = TestingSession()
    onb = db_refresh.query(Onboarding).filter(Onboarding.id == onboarding.id).first()
    assert onb.invitation_email_status.value == "sent"
    assert onb.invitation_sent_at is not None
    db_refresh.close()


# ─── Test: no Resend key → not_sent, no crash ────────────────────────
def test_send_invitation_no_key(hr_user, onboarding_with_candidate, monkeypatch):
    """When RESEND_API_KEY is absent the service records not_sent and does not raise."""
    onboarding = onboarding_with_candidate
    monkeypatch.setenv("RESEND_API_KEY", "")
    with patch("app.services.email_service.is_email_configured", return_value=False):
        result = client.post(
            f"/api/v1/onboarding/{onboarding.id}/send-invitation",
            headers=_headers_for(hr_user),
        )
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "not_sent"
    assert data["last_error"] is not None  # contains the warning message substring


# ─── Test: provider failure → status → failed ────────────────────────────
def test_send_invitation_provider_failure(hr_user, onboarding_with_candidate, monkeypatch):
    onboarding = onboarding_with_candidate
    with patch("app.services.email_service.is_email_configured", return_value=True):
        with patch("app.services.email_service._send_resend") as mock_send:
            mock_send.side_effect = Exception("rate limit")
            result = client.post(
                f"/api/v1/onboarding/{onboarding.id}/send-invitation",
                headers=_headers_for(hr_user),
            )
    # The endpoint returns 200 with status "failed"; the error is recorded, not re-raised.
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "failed"
    assert "rate limit" in data["last_error"].lower()


# ─── Test: reuse existing valid magic link ─────────────────────────────
def test_send_invitation_reuses_existing_token(hr_user, onboarding_with_candidate, monkeypatch):
    """A second send with a still-valid magic link reuses the same portal URL."""
    onboarding = onboarding_with_candidate

    # 1) First send (creates a magic link)
    with patch("app.services.email_service.is_email_configured", return_value=True):
        with patch("app.services.email_service._send_resend") as mock_send:
            mock_send.return_value = MagicMock(id="m1", status="sent")
            r1 = client.post(
                f"/api/v1/onboarding/{onboarding.id}/send-invitation",
                headers=_headers_for(hr_user),
            )
    assert r1.status_code == 200
    first_url = r1.json()["portal_url"]
    first_token = first_url.rsplit("/", 1)[-1]

    # 2) Reuse: token is still valid -> no new token generated, same URL
    with patch("app.services.email_service.is_email_configured", return_value=True):
        with patch("app.services.email_service._send_resend") as mock_send:
            mock_send.return_value = MagicMock(id="m2", status="sent")
            r2 = client.post(
                f"/api/v1/onboarding/{onboarding.id}/send-invitation",
                headers=_headers_for(hr_user),
            )
    assert r2.status_code == 200
    assert r2.json()["portal_url"] == first_url  # same token reused
    assert r2.json()["portal_url"].rsplit("/", 1)[-1] == first_token


# ─── Test: invitation-status endpoint ───────────────────────────────────
def test_invitation_status_endpoint(hr_user, onboarding_with_candidate):
    onboarding = onboarding_with_candidate
    # No send yet → not_sent (auth required even for GET)
    r = client.get(
        f"/api/v1/onboarding/{onboarding.id}/invitation-status",
        headers=_headers_for(hr_user),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_sent"
    assert data["sent_at"] is None
    assert data["last_error"] is None
    assert data["candidate_email"] == onboarding.candidate.email

    # After a send (mocked)
    with patch("app.services.email_service.is_email_configured", return_value=True):
        with patch("app.services.email_service._send_resend") as mock_send:
            mock_send.return_value = MagicMock(id="m", status="sent")
            client.post(f"/api/v1/onboarding/{onboarding.id}/send-invitation",
                        headers=_headers_for(hr_user))
    status = client.get(
        f"/api/v1/onboarding/{onboarding.id}/invitation-status",
        headers=_headers_for(hr_user),
    ).json()
    assert status["status"] == "sent"
    assert status["sent_at"] is not None


# ─── Test: invalid/nonexistent onboarding_id ───────────────────────────
def test_invalid_onboarding_id(hr_user):
    resp = client.post("/api/v1/onboarding/00000000-0000-0000-0000-000000000000/send-invitation", headers=_headers_for(hr_user))
    assert resp.status_code == 404
    resp = client.get("/api/v1/onboarding/00000000-0000-0000-0000-000000000000/invitation-status", headers=_headers_for(hr_user))
    assert resp.status_code == 404
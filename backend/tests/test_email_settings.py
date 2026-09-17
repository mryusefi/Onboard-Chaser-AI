"""Tests for maintenance pass Item 1 / 1b — email settings, status, template.

Covers:
- is_email_configured(): placeholder `re_your_api_key_here` counts as NOT
  configured (root cause of the "Invitation failed — check RESEND_API_KEY"
  report: the .env ships that placeholder and the old bool() check treated it
  as configured, so every send failed at the provider instead of explaining).
- GET /settings/email-status: booleans only, never the key value; setup_hint
  present when unconfigured.
- POST /settings/email-status/test: not_sent w/ hint when unconfigured; sent
  (mocked SDK) when configured; failure path.
- GET/PUT /settings/email-template: defaults when unset, update persists,
  validation bounds (subject ≤200, text ≤2000), auth required.
- send_invitation returns the improved not-configured message (not a 500).
"""
import importlib
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, pwd_context
from app.models.models import User
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"email_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Email HR",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ────────────────────────────────────────────────────────────────────────
# is_email_configured / placeholder detection
# ────────────────────────────────────────────────────────────────────────
class TestEmailConfigured:
    def test_placeholder_key_is_not_configured(self, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_your_api_key_here")
        assert es._is_placeholder_key("re_your_api_key_here") is True
        assert es._is_placeholder_key("") is True
        assert es._is_placeholder_key("your_api_key_here") is True
        # a realistic real key shape must count as configured
        assert es._is_placeholder_key("re_AbCdEf1234567890") is False

    def test_placeholder_env_yields_not_configured(self, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_your_api_key_here")
        mod = importlib.reload(es)
        assert mod.is_email_configured() is False
        importlib.reload(es)  # restore module state for other tests


# ────────────────────────────────────────────────────────────────────────
# GET /settings/email-status
# ────────────────────────────────────────────────────────────────────────
class TestEmailStatusEndpoint:
    def test_requires_auth(self):
        assert client.get("/api/v1/settings/email-status").status_code == 401

    def test_unconfigured_reports_hint_and_no_key(self, hr_user, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_your_api_key_here")
        importlib.reload(es)
        try:
            resp = client.get("/api/v1/settings/email-status",
                              headers=_headers_for(hr_user))
            assert resp.status_code == 200
            data = resp.json()
            assert data["resend_configured"] is False
            assert data["email_from"] is None  # nothing exposed when off
            assert "administrator" in data["setup_hint"]
            assert "RESEND_API_KEY" in data["setup_hint"]
            # never leak the key value
            assert "re_your" not in resp.text
        finally:
            importlib.reload(es)

    def test_configured_reports_from_address_only(self, hr_user, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_AbCdEf1234567890")
        importlib.reload(es)
        try:
            resp = client.get("/api/v1/settings/email-status",
                              headers=_headers_for(hr_user))
            data = resp.json()
            assert data["resend_configured"] is True
            assert data["email_from"]  # from-address visible
            assert "re_AbCdEf" not in resp.text  # key never leaks
            assert data["setup_hint"] is None
        finally:
            importlib.reload(es)


# ────────────────────────────────────────────────────────────────────────
# POST /settings/email-status/test
# ────────────────────────────────────────────────────────────────────────
class TestEmailTestEndpoint:
    def test_requires_auth(self):
        assert client.post("/api/v1/settings/email-status/test").status_code == 401

    def test_not_configured_returns_not_sent_with_hint(self, hr_user, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_your_api_key_here")
        importlib.reload(es)
        try:
            resp = client.post("/api/v1/settings/email-status/test",
                               headers=_headers_for(hr_user))
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "not_sent"
            assert "administrator" in data["message"]
        finally:
            importlib.reload(es)

    def test_configured_sends_to_logged_in_hr(self, hr_user, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_AbCdEf1234567890")
        importlib.reload(es)
        try:
            # Patch the stable SDK entrypoint (module reload recreates module
            # objects, so patching es._send_resend races the reload).
            mock_send = MagicMock(return_value=MagicMock(id="test-email-1"))
            with patch("resend.Emails.send", mock_send):
                resp = client.post("/api/v1/settings/email-status/test",
                                   headers=_headers_for(hr_user))
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "sent"
            assert data["sent_to"] == hr_user.email
            params = mock_send.call_args.args[0]
            assert params["to"] == [hr_user.email]
        finally:
            importlib.reload(es)

    def test_provider_failure_reported(self, hr_user, monkeypatch):
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_AbCdEf1234567890")
        importlib.reload(es)
        try:
            with patch("resend.Emails.send",
                       MagicMock(side_effect=Exception("invalid key"))):
                resp = client.post("/api/v1/settings/email-status/test",
                                   headers=_headers_for(hr_user))
            assert resp.status_code == 200  # handled, not a 500
            assert resp.json()["status"] == "failed"
            assert "invalid key" in resp.json()["message"]
        finally:
            importlib.reload(es)


# ────────────────────────────────────────────────────────────────────────
# Invitation flow uses the improved message (regression for the report)
# ────────────────────────────────────────────────────────────────────────
class TestInvitationNotConfiguredMessage:
    def test_send_invitation_returns_hint_not_500(self, db, hr_user, monkeypatch):
        from app.models.models import Candidate, Onboarding
        import app.services.email_service as es

        monkeypatch.setenv("RESEND_API_KEY", "re_your_api_key_here")
        importlib.reload(es)
        try:
            cand = Candidate(email=f"inv_{uuid.uuid4().hex[:6]}@test.com",
                             full_name="Inv Test", created_by=hr_user.id)
            db.add(cand); db.commit(); db.refresh(cand)
            onb = Onboarding(candidate_id=cand.id)
            db.add(onb); db.commit(); db.refresh(onb)

            result = es.send_invitation(
                candidate_name=cand.full_name,
                company_name="ACME",
                position=cand.position,
                candidate_email=cand.email,
                onboarding_id=onb.id,
                db=db,
            )
            assert result["status"] == "not_sent"
            assert result["last_error"].startswith(
                "Email sending is not configured on this server"
            )
        finally:
            importlib.reload(es)


# ────────────────────────────────────────────────────────────────────────
# Email template (Item 1b)
# ────────────────────────────────────────────────────────────────────────
class TestEmailTemplate:
    def test_requires_auth(self):
        assert client.get("/api/v1/settings/email-template").status_code == 401
        assert client.put("/api/v1/settings/email-template",
                          json={"body_intro": "x"}).status_code == 401

    def test_get_defaults_when_never_customized(self, hr_user):
        resp = client.get("/api/v1/settings/email-template",
                          headers=_headers_for(hr_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_template"] is None
        assert data["body_intro"] is None

    def test_put_persists_and_get_returns_it(self, hr_user):
        payload = {
            "subject_template": "Welcome to {company_name}, {candidate_first_name}!",
            "body_intro": "Hello {candidate_first_name}, welcome aboard!",
            "body_closing": "We're excited to have you.",
            "extra_instructions": "Please use your legal name.",
        }
        r = client.put("/api/v1/settings/email-template", json=payload,
                       headers=_headers_for(hr_user))
        assert r.status_code == 200
        assert r.json()["subject_template"] == payload["subject_template"]
        g = client.get("/api/v1/settings/email-template", headers=_headers_for(hr_user))
        assert g.json() == payload

    def test_subject_over_200_rejected(self, hr_user):
        r = client.put("/api/v1/settings/email-template",
                       json={"subject_template": "x" * 201},
                       headers=_headers_for(hr_user))
        assert r.status_code == 422

    def test_body_over_2000_rejected(self, hr_user):
        r = client.put("/api/v1/settings/email-template",
                       json={"body_intro": "x" * 2001},
                       headers=_headers_for(hr_user))
        assert r.status_code == 422

    def test_render_honors_template_config(self, hr_user):
        from app.services.email_service import render_invitation_email

        html = render_invitation_email(
            candidate_name="Sara Ahmadi", company_name="ACME", position="Dev",
            portal_url="http://x/onboard/t", expiry_hours=72,
            docs=[{"name": "ID"}],
            template_config={
                "subject_template": "Welcome {candidate_first_name}!",
                "body_intro": "Custom intro for Sara.",
                "body_closing": "Custom closing.",
                "extra_instructions": "Bring your badge.",
            },
        )
        assert "Custom intro for Sara." in html
        assert "Custom closing." in html
        assert "Bring your badge." in html
        # functional parts remain
        assert "http://x/onboard/t" in html
        assert "ACME" in html

    def test_render_without_config_uses_builtin(self, hr_user):
        from app.services.email_service import render_invitation_email

        html = render_invitation_email(
            candidate_name="Sara Ahmadi", company_name="ACME", position="Dev",
            portal_url="http://x/onboard/t", expiry_hours=72, docs=[{"name": "ID"}],
        )
        assert "Hello Sara Ahmadi" in html
        assert "Custom intro" not in html

    def test_plain_text_render_honors_template(self):
        from app.services.email_service import render_plain_text

        text = render_plain_text(
            candidate_name="Sara Ahmadi", company_name="ACME", position="Dev",
            portal_url="http://x/onboard/t", expiry_hours=72, docs=[{"name": "ID"}],
            template_config={"body_intro": "Plain intro.", "body_closing": "Plain close."},
        )
        assert "Plain intro." in text
        assert "Plain close." in text
        assert "http://x/onboard/t" in text

    def test_subject_format_safety(self, db, hr_user, monkeypatch):
        """
        An invitation subject containing braces that aren't our placeholders
        ({unknown_var}, {0}) must NOT crash the send — unknown names stay
        literal and numeric fields are escaped, so HR can paste arbitrary
        text without triggering KeyError/IndexError -> 500.
        """
        import uuid as _uuid
        import app.services.email_service as es
        from app.models.models import Candidate, Onboarding, EmailTemplateConfig

        monkeypatch.setenv("RESEND_API_KEY", "re_AbCdEf1234567890")
        importlib.reload(es)
        try:
            row = EmailTemplateConfig(
                id=1,
                subject_template="Welcome {candidate_first_name} {unknown_var} {0}",
            )
            db.add(row); db.commit()

            cand = Candidate(email=f"subj_{_uuid.uuid4().hex[:6]}@test.com",
                             full_name="Sara Ahmadi", created_by=hr_user.id)
            db.add(cand); db.commit(); db.refresh(cand)
            onb = Onboarding(candidate_id=cand.id)
            db.add(onb); db.commit(); db.refresh(onb)

            mock_send = MagicMock(return_value=MagicMock(id="n1"))
            with patch("resend.Emails.send", mock_send):
                result = es.send_invitation(
                    candidate_name="Sara Ahmadi", company_name="ACME",
                    position="Dev", candidate_email=cand.email,
                    onboarding_id=onb.id, db=db,
                )
            assert result["status"] == "sent"
            subject_used = mock_send.call_args.args[0]["subject"]
            assert "Sara" in subject_used          # real placeholder resolved
            assert "{unknown_var}" in subject_used  # unknown stays literal
            assert "{0}" in subject_used            # numeric stays literal
        finally:
            importlib.reload(es)

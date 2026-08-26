"""Tests for US01: Secure Onboarding Portal"""
import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.models.models import Candidate, Onboarding, User, Document
from app.core.security import pwd_context, validate_magic_token, create_magic_token
from tests.conftest import TestingSession, make_hr_headers

client = TestClient(app)


@pytest.fixture
def hr_user(db):
    user = User(
        email="hr@test.com",
        full_name="Test HR",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def candidate(db, hr_user):
    candidate = Candidate(
        email="candidate@test.com",
        full_name="Test Candidate",
        phone="+1234567890",
        position="Software Engineer",
        created_by=hr_user.id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


# ============================================================
# US01 Task Tests
# ============================================================


class TestCreateOnboardingPage:
    """Task: Create candidate onboarding page (API endpoint)."""

    def test_start_onboarding_creates_record(self, candidate):
        resp = client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_id"] == str(candidate.id)
        assert data["status"] == "pending"

    def test_start_onboarding_invalid_id(self):
        resp = client.post(
            "/api/v1/onboarding/not-a-uuid", headers=make_hr_headers()
        )
        assert resp.status_code == 400

    def test_duplicate_onboarding_rejected(self, candidate):
        client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        resp = client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        assert resp.status_code == 409


class TestCreateUniqueURL:
    """Task: Create unique onboarding URL."""

    def test_magic_link_generation(self, candidate):
        client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        resp = client.post(
            "/api/v1/onboarding/magic-link",
            json={"candidate_id": str(candidate.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "magic_link" in data
        assert "/onboard/" in data["magic_link"]
        assert "expires_at" in data


class TestSecureAccessToken:
    """Task: Generate secure access token."""

    def test_token_encoding_decoding(self, candidate):
        token = create_magic_token(str(candidate.id), candidate.email)
        payload = validate_magic_token(token)
        assert payload is not None
        assert payload["sub"] == str(candidate.id)
        assert payload["email"] == candidate.email
        assert payload["type"] == "magic"

    def test_invalid_token_rejected(self):
        payload = validate_magic_token("invalid.token.here")
        assert payload is None

    def test_non_magic_token_rejected(self):
        from app.core.security import create_access_token
        token = create_access_token({"sub": "user123"})
        payload = validate_magic_token(token)
        assert payload is None


class TestTokenExpiration:
    """Task: Add token expiration mechanism."""

    def test_expired_token_rejected(self, candidate):
        from jose import jwt
        from app.core.config import settings

        expired_payload = {
            "sub": str(candidate.id),
            "email": candidate.email,
            "type": "magic",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm="HS256")
        payload = validate_magic_token(token)
        assert payload is None


class TestValidateCandidateAccess:
    """Task: Validate candidate access request."""

    def test_valid_token_accesses_portal(self, candidate):
        client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        resp = client.post(
            "/api/v1/onboarding/magic-link",
            json={"candidate_id": str(candidate.id)},
        )
        token_url = resp.json()["magic_link"]
        token = token_url.split("/onboard/")[1]

        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_name"] == "Test Candidate"
        assert data["candidate_email"] == "candidate@test.com"
        assert len(data["documents"]) == 4

    def test_invalid_token_returns_403(self):
        resp = client.get("/api/v1/onboarding/portal/invalid-token")
        assert resp.status_code == 403


class TestBasicOnboardingSession:
    """Task: Create basic onboarding session."""

    def test_session_marks_started(self, candidate, db):
        client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        resp = client.post(
            "/api/v1/onboarding/magic-link",
            json={"candidate_id": str(candidate.id)},
        )
        token = resp.json()["magic_link"].split("/onboard/")[1]
        client.get(f"/api/v1/onboarding/portal/{token}")

        onboarding = db.query(Onboarding).filter(
            Onboarding.candidate_id == candidate.id
        ).first()
        assert onboarding.status.value == "in_progress"
        assert onboarding.is_token_used is True
        assert onboarding.started_at is not None

    def test_default_documents_created(self, candidate, db):
        client.post(f"/api/v1/onboarding/{candidate.id}", headers=make_hr_headers())
        onboarding = db.query(Onboarding).filter(
            Onboarding.candidate_id == candidate.id
        ).first()
        docs = db.query(Document).filter(
            Document.onboarding_id == onboarding.id
        ).all()
        doc_names = [d.name for d in docs]
        assert "Government ID" in doc_names
        assert "Proof of Address" in doc_names
        assert "Tax Form (W-4)" in doc_names
        assert "Signed Offer Letter" in doc_names

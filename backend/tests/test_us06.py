"""Tests for US06: HR Onboarding Creation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from uuid import UUID

from app.main import app
from app.models.models import User, Candidate, Onboarding, Document, OnboardingStatus
from app.core.security import pwd_context
from tests.conftest import TestingSession

client = TestClient(app)


@pytest.fixture
def hr_user(db):
    user = User(
        email="hr6@test.com",
        full_name="HR Six",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_headers(db):
    """Login as an existing HR user and return Authorization headers."""
    # Use the API to get a token (register is idempotent-checked by email).
    resp = client.post("/api/v1/auth/login", json={"email": "hr6@test.com", "password": "password123"})
    if resp.status_code != 200:
        # hr_user fixture not committed yet in this session; create via API
        client.post("/api/v1/auth/register", json={
            "email": "hr6b@test.com", "full_name": "HR Six B", "password": "password123"
        })
        resp = client.post("/api/v1/auth/login", json={"email": "hr6b@test.com", "password": "password123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(hr_user):
    return {
        "Authorization": (
            "Bearer "
            + __import__("app.core.security", fromlist=["create_access_token"])
            .create_access_token(data={"sub": str(hr_user.id), "email": hr_user.email})
        )
    }


CANDIDATE_PAYLOAD = {
    "full_name": "Jane Newhire",
    "email": "jane@acme.com",
    "phone": "+15551234567",
    "position": "Backend Engineer",
}


class TestCandidateCreation:
    """Task: complete candidate creation endpoint (HR auth)."""

    def test_create_candidate_success(self, headers):
        resp = client.post("/api/v1/candidates/", json=CANDIDATE_PAYLOAD, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == CANDIDATE_PAYLOAD["full_name"]
        assert data["email"] == CANDIDATE_PAYLOAD["email"]
        assert data["position"] == CANDIDATE_PAYLOAD["position"]

    def test_create_candidate_duplicate_email_conflict(self, headers):
        client.post("/api/v1/candidates/", json=CANDIDATE_PAYLOAD, headers=headers)
        resp = client.post("/api/v1/candidates/", json=CANDIDATE_PAYLOAD, headers=headers)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_candidate_requires_auth(self):
        resp = client.post("/api/v1/candidates/", json=CANDIDATE_PAYLOAD)
        assert resp.status_code == 401


class TestOnboardingCreation:
    """Task: onboarding creation for existing candidate (HR auth)."""

    def _create_candidate(self, headers, email="onb@acme.com"):
        r = client.post(
            "/api/v1/candidates/",
            json={**CANDIDATE_PAYLOAD, "email": email},
            headers=headers,
        )
        return r.json()["id"]

    def test_onboarding_with_default_documents(self, headers):
        cand_id = self._create_candidate(headers)
        resp = client.post(f"/api/v1/onboarding/{cand_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["candidate_id"] == cand_id
        # Verify 4 default docs were seeded
        db = TestingSession()
        docs = db.query(Document).filter(Document.onboarding_id == UUID(data["id"])).all()
        db.close()
        assert len(docs) == 4
        names = {d.name for d in docs}
        assert "Government ID" in names and "Tax Form (W-4)" in names

    def test_onboarding_with_custom_documents_replaces_defaults(self, headers):
        cand_id = self._create_candidate(headers, "custom@acme.com")
        custom_docs = [
            {
                "name": "Background Check Consent",
                "description": "Signed consent form",
                "instructions": "Sign and date the background check consent.",
                "accepted_formats": "PDF",
                "required": True,
            },
            {
                "name": "Bank Details Form",
                "description": None,
                "instructions": "Provide your payroll bank details.",
                "accepted_formats": "PDF",
                "required": False,
            },
        ]
        resp = client.post(
            f"/api/v1/onboarding/{cand_id}",
            json={"candidate_id": cand_id, "required_documents": custom_docs},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        db = TestingSession()
        docs = db.query(Document).filter(Document.onboarding_id == UUID(data["id"])).all()
        db.close()
        assert len(docs) == 2  # replaced, NOT appended
        names = {d.name for d in docs}
        assert names == {"Background Check Consent", "Bank Details Form"}
        optional_doc = next(d for d in docs if d.name == "Bank Details Form")
        assert optional_doc.required is False

    def test_onboarding_duplicate_rejected_409(self, headers):
        cand_id = self._create_candidate(headers, "dup@acme.com")
        first = client.post(f"/api/v1/onboarding/{cand_id}", headers=headers)
        assert first.status_code == 200
        second = client.post(f"/api/v1/onboarding/{cand_id}", headers=headers)
        assert second.status_code == 409

    def test_onboarding_unknown_candidate_404(self, headers):
        fake = "00000000-0000-0000-0000-000000000099"
        resp = client.post(f"/api/v1/onboarding/{fake}", headers=headers)
        assert resp.status_code == 404

    def test_onboarding_requires_auth(self, headers):
        cand_id = self._create_candidate(headers, "noauth@acme.com")
        resp = client.post(f"/api/v1/onboarding/{cand_id}")
        assert resp.status_code == 401

    def test_onboarding_invalid_uuid_400(self, headers):
        resp = client.post("/api/v1/onboarding/not-a-uuid", headers=headers)
        assert resp.status_code == 400


class TestCreateFullEndpoint:
    """Task: combined convenience endpoint POST /onboarding/create-full."""

    def test_create_full_defaults(self, headers):
        payload = {"candidate": CANDIDATE_PAYLOAD}
        resp = client.post("/api/v1/onboarding/create-full", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate"]["email"] == CANDIDATE_PAYLOAD["email"]
        assert data["onboarding"]["status"] == "pending"
        assert len(data["documents"]) == 4
        assert all(d["status"] == "pending" for d in data["documents"])

    def test_create_full_with_custom_documents(self, headers):
        payload = {
            "candidate": {**CANDIDATE_PAYLOAD, "email": "fullcust@acme.com"},
            "required_documents": [
                {
                    "name": "Visa Copy",
                    "description": None,
                    "instructions": "Upload your work visa.",
                    "accepted_formats": "PDF",
                    "required": True,
                },
            ],
        }
        resp = client.post("/api/v1/onboarding/create-full", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["name"] == "Visa Copy"

    def test_create_full_duplicate_email_409(self, headers):
        payload = {"candidate": CANDIDATE_PAYLOAD}
        client.post("/api/v1/onboarding/create-full", json=payload, headers=headers)
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={**payload, "candidate": {**CANDIDATE_PAYLOAD}},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_create_full_requires_auth(self):
        resp = client.post("/api/v1/onboarding/create-full", json={"candidate": CANDIDATE_PAYLOAD})
        assert resp.status_code == 401

    def test_create_full_missing_required_fields_422(self, headers):
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": {"email": "missingname@acme.com"}},
            headers=headers,
        )
        assert resp.status_code == 422


class TestValidationErrors:
    """Task: input validation errors."""

    def test_candidate_missing_email_422(self, headers):
        resp = client.post(
            "/api/v1/candidates/", json={"full_name": "No Email"}, headers=headers
        )
        assert resp.status_code == 422

    def test_candidate_missing_full_name_422(self, headers):
        resp = client.post(
            "/api/v1/candidates/", json={"email": "x@y.com"}, headers=headers
        )
        assert resp.status_code == 422

    def test_custom_document_missing_name_422(self, headers):
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={
                "candidate": CANDIDATE_PAYLOAD,
                "required_documents": [{"accepted_formats": "PDF"}],
            },
            headers=headers,
        )
        assert resp.status_code == 422

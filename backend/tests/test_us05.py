"""Tests for US05: Document Status Tracking."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from uuid import UUID

from app.main import app
from app.models.models import User, Candidate, Onboarding, Document, DocumentStatus, OnboardingStatus
from app.core.security import pwd_context
from app.services.onboarding_service import (
    compute_completion_percentage,
    update_document_status,
)
from tests.conftest import TestingSession, make_hr_headers

client = TestClient(app)


@pytest.fixture
def onboarding_with_docs(db):
    """HR + candidate + onboarding + 4 docs; returns (onboarding, doc_ids)."""
    user = User(email="hr5@t.com", full_name="HR5", hashed_password=pwd_context.hash("p"), is_hr=True)
    db.add(user); db.commit(); db.refresh(user)
    cand = Candidate(email="c5@t.com", full_name="C5", created_by=user.id)
    db.add(cand); db.commit(); db.refresh(cand)
    client.post(f"/api/v1/onboarding/{cand.id}", headers=make_hr_headers())
    onb = db.query(Onboarding).filter(Onboarding.candidate_id == cand.id).first()
    docs = db.query(Document).filter(Document.onboarding_id == onb.id).all()
    doc_ids = [str(d.id) for d in docs]
    return onb, doc_ids


class TestDocumentStatusModel:
    """Task: Create document status model (Pending/Uploaded/Completed/Missing)."""

    def test_status_enum_values(self):
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.UPLOADED.value == "uploaded"
        assert DocumentStatus.COMPLETED.value == "completed"
        assert DocumentStatus.MISSING.value == "missing"

    def test_documents_start_pending(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        for did in doc_ids:
            resp = client.get(f"/api/v1/onboarding/document/{did}")
            assert resp.json()["status"] == "pending"

    def test_onboarding_status_enum(self):
        assert OnboardingStatus.PENDING.value == "pending"
        assert OnboardingStatus.IN_PROGRESS.value == "in_progress"
        assert OnboardingStatus.COMPLETED.value == "completed"


class TestStatusAfterUpload:
    """Task: Update status after upload."""

    def test_upload_sets_uploaded(self, onboarding_with_docs, db):
        onb, doc_ids = onboarding_with_docs
        resp = client.post(
            f"/api/v1/onboarding/document/{doc_ids[0]}/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploaded"
        # DB check
        doc = db.query(Document).filter(Document.id == UUID(doc_ids[0])).first()
        assert doc.status == DocumentStatus.UPLOADED

    def test_status_update_to_completed(self, onboarding_with_docs, db):
        onb, doc_ids = onboarding_with_docs
        resp = client.patch(
            f"/api/v1/onboarding/document/{doc_ids[0]}/status",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        doc = db.query(Document).filter(Document.id == UUID(doc_ids[0])).first()
        assert doc.status == DocumentStatus.COMPLETED

    def test_status_update_to_missing(self, onboarding_with_docs, db):
        onb, doc_ids = onboarding_with_docs
        resp = client.patch(
            f"/api/v1/onboarding/document/{doc_ids[1]}/status",
            json={"status": "missing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "missing"

    def test_invalid_status_rejected(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        resp = client.patch(
            f"/api/v1/onboarding/document/{doc_ids[0]}/status",
            json={"status": "nonsense"},
        )
        assert resp.status_code == 400


class TestCompletionPercentage:
    """Task: Display completion percentage."""

    def test_zero_percent_initial(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        resp = client.get(f"/api/v1/onboarding/progress/{onb.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["completion_percentage"] == 0
        assert data["completed_documents"] == 0
        assert data["total_documents"] == 4

    def test_25_percent_one_uploaded(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        client.post(
            f"/api/v1/onboarding/document/{doc_ids[0]}/upload",
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        )
        resp = client.get(f"/api/v1/onboarding/progress/{onb.id}")
        data = resp.json()
        assert data["completion_percentage"] == 25
        assert data["completed_documents"] == 1

    def test_50_percent_two_done(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        client.patch(f"/api/v1/onboarding/document/{doc_ids[0]}/status", json={"status": "completed"})
        client.patch(f"/api/v1/onboarding/document/{doc_ids[1]}/status", json={"status": "completed"})
        resp = client.get(f"/api/v1/onboarding/progress/{onb.id}")
        data = resp.json()
        assert data["completion_percentage"] == 50
        assert data["completed_documents"] == 2

    def test_100_percent_completes_onboarding(self, onboarding_with_docs, db):
        onb, doc_ids = onboarding_with_docs
        for did in doc_ids:
            client.patch(f"/api/v1/onboarding/document/{did}/status", json={"status": "completed"})
        resp = client.get(f"/api/v1/onboarding/progress/{onb.id}")
        data = resp.json()
        assert data["completion_percentage"] == 100
        assert data["completed_documents"] == 4
        # Onboarding should auto-complete (re-query with fresh session state)
        db.expire_all()
        onb = db.query(Onboarding).filter(Onboarding.id == onb.id).first()
        assert onb.status == OnboardingStatus.COMPLETED
        assert onb.completed_at is not None

    def test_progress_invalid_id(self):
        resp = client.get("/api/v1/onboarding/progress/not-a-uuid")
        assert resp.status_code == 400

    def test_progress_not_found(self):
        resp = client.get("/api/v1/onboarding/progress/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestPortalShowsProgress:
    """Task: portal response includes completion stats."""

    def test_portal_response_has_completion(self, onboarding_with_docs):
        onb, doc_ids = onboarding_with_docs
        # Generate magic link + open portal
        cand = onb.candidate
        resp = client.post("/api/v1/onboarding/magic-link", json={"candidate_id": str(cand.id)})
        token = resp.json()["magic_link"].split("/onboard/")[1]
        portal = client.get(f"/api/v1/onboarding/portal/{token}").json()
        assert "completion_percentage" in portal
        assert portal["completion_percentage"] == 0
        assert portal["completed_documents"] == 0
        assert portal["total_documents"] == 4

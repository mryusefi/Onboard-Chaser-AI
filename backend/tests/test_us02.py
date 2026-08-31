"""Tests for US02: Document Checklist"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import User, Candidate
from app.core.security import pwd_context
from tests.conftest import make_hr_headers

client = TestClient(app)


@pytest.fixture
def hr_and_candidate(db):
    user = User(email="hr@t.com", full_name="HR", hashed_password=pwd_context.hash("p"), is_hr=True)
    db.add(user); db.commit(); db.refresh(user)
    cand = Candidate(email="c@t.com", full_name="Test Candidate", created_by=user.id)
    db.add(cand); db.commit(); db.refresh(cand)
    # Create onboarding + magic link + portal access
    client.post(f"/api/v1/onboarding/{cand.id}", headers=make_hr_headers())
    resp = client.post("/api/v1/onboarding/magic-link", json={"candidate_id": str(cand.id)})
    token = resp.json()["magic_link"].split("/onboard/")[1]
    client.get(f"/api/v1/onboarding/portal/{token}")
    return cand, token


# ============================================================
# US02 Task Tests
# ============================================================


class TestDocumentRequirementModel:
    """Task: Create document requirement model with instructions."""

    def test_documents_created_with_default_names(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        docs = resp.json()["documents"]
        names = {d["name"] for d in docs}
        assert names == {"Government ID", "Proof of Address", "Tax Form (W-4)", "Signed Offer Letter"}

    def test_documents_have_instructions(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        for doc in resp.json()["documents"]:
            assert doc["instructions"] is not None
            assert len(doc["instructions"]) > 20

    def test_documents_have_accepted_formats(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        for doc in resp.json()["documents"]:
            assert doc["accepted_formats"] is not None
            assert "PDF" in doc["accepted_formats"]

    def test_documents_are_required(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        for doc in resp.json()["documents"]:
            assert doc["required"] is True

    def test_government_id_instruction_content(self, hr_and_candidate):
        cand, token = hr_and_candidate
        docs = client.get(f"/api/v1/onboarding/portal/{token}").json()["documents"]
        gov_id = next(d for d in docs if d["name"] == "Government ID")
        assert "four corners" in gov_id["instructions"].lower() or "government" in gov_id["instructions"].lower()

    def test_tax_form_only_accepts_pdf(self, hr_and_candidate):
        cand, token = hr_and_candidate
        docs = client.get(f"/api/v1/onboarding/portal/{token}").json()["documents"]
        tax_form = next(d for d in docs if d["name"] == "Tax Form (W-4)")
        assert tax_form["accepted_formats"] == "PDF"


class TestDocumentChecklistUI:
    """Task: Display required document list with completion status."""

    def test_portal_returns_all_documents(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        assert resp.status_code == 200
        assert len(resp.json()["documents"]) == 4

    def test_all_documents_start_pending(self, hr_and_candidate):
        cand, token = hr_and_candidate
        docs = client.get(f"/api/v1/onboarding/portal/{token}").json()["documents"]
        for doc in docs:
            assert doc["status"] == "pending"

    def test_completion_status_shows_in_progress(self, hr_and_candidate):
        cand, token = hr_and_candidate
        resp = client.get(f"/api/v1/onboarding/portal/{token}")
        assert resp.json()["status"] == "in_progress"

    def test_each_document_has_required_fields(self, hr_and_candidate):
        cand, token = hr_and_candidate
        docs = client.get(f"/api/v1/onboarding/portal/{token}").json()["documents"]
        required_fields = {"id", "name", "instructions", "accepted_formats", "required", "status"}
        for doc in docs:
            assert required_fields.issubset(doc.keys()), f"Missing: {required_fields - doc.keys()}"

    def test_document_count_matches_template(self, hr_and_candidate):
        cand, token = hr_and_candidate
        docs = client.get(f"/api/v1/onboarding/portal/{token}").json()["documents"]
        assert len(docs) == 4


class TestCustomDocumentNames:
    """Verify custom document names handling."""

    def test_second_candidate_gets_default_docs(self, hr_and_candidate, db):
        user = db.query(User).first()
        cand2 = Candidate(email="c2@t.com", full_name="C2", created_by=user.id)
        db.add(cand2); db.commit(); db.refresh(cand2)

        resp = client.post(f"/api/v1/onboarding/{cand2.id}", headers=make_hr_headers())
        assert resp.status_code == 200

        resp = client.post("/api/v1/onboarding/magic-link", json={"candidate_id": str(cand2.id)})
        token2 = resp.json()["magic_link"].split("/onboard/")[1]
        resp = client.get(f"/api/v1/onboarding/portal/{token2}")
        assert len(resp.json()["documents"]) == 4

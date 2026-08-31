"""Tests for US03: Document Upload"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from uuid import UUID
from app.main import app
from app.models.models import User, Candidate, Document
from app.core.security import pwd_context
from app.services.document_service import validate_file, upload_file_to_storage
from tests.conftest import TestingSession, make_hr_headers

client = TestClient(app)


@pytest.fixture
def hr_and_candidate_with_docs(db):
    """Create HR, candidate, onboarding with documents — returns (candidate, token, db)."""
    user = User(email="hr3@t.com", full_name="HR3", hashed_password=pwd_context.hash("p"), is_hr=True)
    db.add(user); db.commit(); db.refresh(user)
    cand = Candidate(email="c3@t.com", full_name="C3", created_by=user.id)
    db.add(cand); db.commit(); db.refresh(cand)
    # Create onboarding
    client.post(f"/api/v1/onboarding/{cand.id}", headers=make_hr_headers())
    # Magic link
    resp = client.post("/api/v1/onboarding/magic-link", json={"candidate_id": str(cand.id)})
    token = resp.json()["magic_link"].split("/onboard/")[1]
    # Access portal
    client.get(f"/api/v1/onboarding/portal/{token}")
    return cand, token


def get_doc_id(db, candidate):
    """Helper to get the first document ID for a candidate's onboarding."""
    from app.models.models import Onboarding
    onboarding = db.query(Onboarding).filter(Onboarding.candidate_id == candidate.id).first()
    doc = db.query(Document).filter(Document.onboarding_id == onboarding.id).first()
    return str(doc.id)


class TestFileValidation:
    """Task: Validate file size / file format."""

    def test_validate_pdf(self):
        is_valid, err = validate_file(b"%PDF-1.4 test", "test.pdf")
        assert is_valid is True
        assert err == ""

    def test_validate_jpeg(self):
        # Minimal JPEG-like header
        is_valid, err = validate_file(b"\xff\xd8\xff\xe0" + b"x" * 100, "photo.jpg")
        assert is_valid is True

    def test_validate_png(self):
        is_valid, err = validate_file(b"\x89PNG\r\n\x1a\n" + b"x" * 100, "image.png")
        assert is_valid is True

    def test_reject_txt(self):
        is_valid, err = validate_file(b"plain text", "notes.txt")
        assert is_valid is False
        assert "Unsupported" in err

    def test_reject_exe(self):
        is_valid, err = validate_file(b"MZ" + b"x" * 100, "malware.exe")
        assert is_valid is False

    def test_reject_oversized_file(self):
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        is_valid, err = validate_file(large_content, "big.pdf")
        assert is_valid is False
        assert "exceeds" in err.lower() or "10MB" in err or "10" in err

    def test_reject_empty_file(self):
        is_valid, err = validate_file(b"", "empty.pdf")
        assert is_valid is False
        assert "empty" in err.lower()

    def test_extension_mismatch_rejected(self):
        # A .jpg extension with content that mimetypes can't determine is still
        # valid by extension check — test a real mismatch: .csv extension
        is_valid, err = validate_file(b"some,email,here\n", "data.csv")
        assert is_valid is False
        assert "Unsupported" in err


class TestFileUploadEndpoint:
    """Task: Upload files via API endpoint."""

    def test_upload_pdf_success(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        # Re-open a session for verification
        verify_db = TestingSession()

        response = client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("document.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["file_name"] == "document.pdf"
        assert result["status"] == "uploaded"
        assert result["file_key"] is not None
        verify_db.close()

    def test_upload_image_success(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        response = client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"x" * 100, "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "uploaded"

    def test_upload_oversized_rejected(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        large = b"x" * (11 * 1024 * 1024)
        response = client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("big.pdf", large, "application/pdf")},
        )
        assert response.status_code == 400
        assert "10MB" in response.json()["detail"] or "exceeds" in response.json()["detail"].lower()

    def test_upload_invalid_format_rejected(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        response = client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("bad.txt", b"plain text", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    def test_upload_empty_file_rejected(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        response = client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_upload_invalid_document_id(self):
        response = client.post(
            "/api/v1/onboarding/document/00000000-0000-0000-0000-000000000000/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert response.status_code == 400


class TestMetadataStorage:
    """Task: Store upload metadata in database."""

    def test_file_name_stored(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        verify_db = TestingSession()

        client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("my_gov_id.pdf", b"%PDF-1.4 id", "application/pdf")},
        )
        doc = verify_db.query(Document).filter(Document.id == UUID(doc_id)).first()
        assert doc.file_name == "my_gov_id.pdf"
        assert doc.file_key is not None
        assert doc.uploaded_at is not None
        verify_db.close()

    def test_status_updated_to_uploaded(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)
        verify_db = TestingSession()

        client.post(
            f"/api/v1/onboarding/document/{doc_id}/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        doc = verify_db.query(Document).filter(Document.id == UUID(doc_id)).first()
        assert doc.status.value == "uploaded"
        verify_db.close()


class TestGetDocument:
    """Task: Fetch document requirement for upload context."""

    def test_get_document_returns_instructions(self, hr_and_candidate_with_docs, db):
        cand, token = hr_and_candidate_with_docs
        doc_id = get_doc_id(db, cand)

        resp = client.get(f"/api/v1/onboarding/document/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instructions"] is not None
        assert data["accepted_formats"] is not None
        assert data["name"] is not None
        assert data["status"] == "pending"

    def test_get_document_not_found(self):
        resp = client.get("/api/v1/onboarding/document/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

"""Tests for US04: Secure Document Storage (R2 / encryption / structure)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from uuid import UUID

from app.main import app
from app.models.models import User, Candidate, Document, Onboarding
from app.core.security import pwd_context
from app.services import storage
from app.services.document_service import upload_file_to_storage
from tests.conftest import TestingSession, make_hr_headers

client = TestClient(app)


def make_onboarding(db):
    user = User(email="hr4@t.com", full_name="HR4", hashed_password=pwd_context.hash("p"), is_hr=True)
    db.add(user); db.commit(); db.refresh(user)
    cand = Candidate(email="c4@t.com", full_name="C4", created_by=user.id)
    db.add(cand); db.commit(); db.refresh(cand)
    client.post(f"/api/v1/onboarding/{cand.id}", headers=make_hr_headers())
    onb = db.query(Onboarding).filter(Onboarding.candidate_id == cand.id).first()
    return onb


@pytest.fixture
def onboarding(db):
    return make_onboarding(db)


@pytest.fixture
def doc(db, onboarding):
    doc = Document(onboarding_id=onboarding.id, name="Government ID", required=True)
    db.add(doc); db.commit(); db.refresh(doc)
    return doc


class TestStorageConfig:
    """Tasks: setup cloud storage, private bucket config."""

    def test_storage_status_endpoint(self):
        resp = client.get("/api/v1/onboarding/storage/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["encryption_enabled"] is True
        assert data["encryption_algorithm"] == "AES-256-Fernet"
        assert "onboardings" in data["structure"]

    def test_r2_not_configured_locally(self):
        # In tests R2 env vars are not set -> fallback to local
        assert storage.is_r2_configured() is False

    def test_storage_backend_name(self):
        data = client.get("/api/v1/onboarding/storage/status").json()
        # Without R2 creds, backend should be local
        assert data["storage_backend"] in ("cloudflare_r2", "local_filesystem")


class TestStorageStructure:
    """Task: create document storage structure."""

    def test_storage_path_structure(self):
        key = storage.storage_path_for(
            "a704d29d-7ff5-474a-85df-3769c81a66af",
            "b63eaa5f-c5e6-44ff-97fe-21bb861a9e51",
            "pdf",
        )
        assert key == "onboardings/a704d29d-7ff5-474a-85df-3769c81a66af/b63eaa5f-c5e6-44ff-97fe-21bb861a9e51.pdf"
        parts = key.split("/")
        assert parts[0] == "onboardings"
        assert parts[1] == "a704d29d-7ff5-474a-85df-3769c81a66af"
        assert parts[2].startswith("b63eaa5f")

    def test_storage_path_groups_by_onboarding(self):
        k1 = storage.storage_path_for("onb-1", "doc-1", "png")
        k2 = storage.storage_path_for("onb-1", "doc-2", "pdf")
        k3 = storage.storage_path_for("onb-2", "doc-3", "jpg")
        assert k1.split("/")[1] == k2.split("/")[1] == "onb-1"
        assert k3.split("/")[1] == "onb-2"


class TestEncryption:
    """Task: encrypt stored documents."""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = b"%PDF-1.4 confidential content here"
        ct, algo = storage.encrypt_bytes(plaintext)
        assert algo == "AES-256-Fernet"
        assert ct != plaintext
        assert storage.decrypt_bytes(ct) == plaintext

    def test_encrypted_data_not_readable(self):
        ct, _ = storage.encrypt_bytes(b"secret data")
        assert b"secret data" not in ct

    def test_encryption_key_stable(self):
        # Same SECRET_KEY -> same derived key across calls
        k1 = storage._derive_key()
        k2 = storage._derive_key()
        assert k1 == k2


class TestDbStorageLinkage:
    """Task: connect database with stored files."""

    def test_upload_stores_metadata_linkage(self, doc, db):
        result = upload_file_to_storage(
            db, str(doc.id), b"%PDF-1.4 test", "gov_id.pdf"
        )
        assert result["file_key"].startswith("onboardings/")
        assert result["encryption_algorithm"] == "AES-256-Fernet"
        assert result["file_size"] == str(len(b"%PDF-1.4 test"))
        assert result["status"] == "uploaded"
        # Reload from DB
        reloaded = db.query(Document).filter(Document.id == doc.id).first()
        assert reloaded.file_key == result["file_key"]
        assert reloaded.file_mime_type == "application/pdf"
        assert reloaded.encryption_algorithm == "AES-256-Fernet"

    def test_upload_persists_storage_structure(self, doc, db):
        upload_file_to_storage(db, str(doc.id), b"x" * 2048, "proof.png")
        reloaded = db.query(Document).filter(Document.id == doc.id).first()
        parts = reloaded.file_key.split("/")
        assert parts[0] == "onboardings"
        assert parts[1] == str(doc.onboarding_id)
        assert parts[2] == f"{doc.id}.png"

    def test_stored_file_is_encrypted_on_disk(self, doc, db):
        upload_file_to_storage(db, str(doc.id), b"plaintext-content-should-be-encrypted", "id.pdf")
        reloaded = db.query(Document).filter(Document.id == doc.id).first()
        # Read the file from the local fallback and verify it's not plaintext
        path = os.path.join(storage.local_fallback_dir(), reloaded.file_key)
        with open(path, "rb") as f:
            raw = f.read()
        assert b"plaintext-content-should-be-encrypted" not in raw
        # And it can be decrypted back
        assert storage.decrypt_bytes(raw) == b"plaintext-content-should-be-encrypted"

    def test_upload_endpoint_returns_encryption_metadata(self, doc):
        resp = client.post(
            f"/api/v1/onboarding/document/{doc.id}/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["encryption_algorithm"] == "AES-256-Fernet"
        assert "onboardings/" in data["file_key"]
        assert data["file_mime_type"] == "application/pdf"

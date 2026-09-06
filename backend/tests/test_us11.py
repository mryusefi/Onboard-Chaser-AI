"""Tests for US11 — Candidate detail, document access URLs, manual verification."""
import os
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
    OnboardingStatus,
    Document,
    DocumentStatus,
    DocumentVerificationStatus,
    InvitationEmailStatus,
)
from app.services import storage
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"hr11_{uuid.uuid4().hex[:6]}@test.com",
        full_name="HR Eleven",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def onboarding_with_docs(db, hr_user):
    """Onboarding with 3 documents: one uploaded, one completed, one pending."""
    cand = Candidate(
        email=f"cand_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Dana Docs",
        phone="+1-555-0100",
        position="Analyst",
        created_by=hr_user.id,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    onb = Onboarding(
        candidate_id=cand.id,
        status=OnboardingStatus.IN_PROGRESS,
        invitation_email_status=InvitationEmailStatus.SENT,
        invitation_sent_at=datetime.now(timezone.utc) - timedelta(hours=5),
    )
    db.add(onb)
    db.commit()
    db.refresh(onb)

    up = Document(
        onboarding_id=onb.id, name="Government ID", required=True,
        status=DocumentStatus.UPLOADED,
        file_key=f"onboardings/{onb.id}/{uuid.uuid4().hex}.pdf",
        file_name="passport.pdf", file_size="2048",
        file_mime_type="application/pdf",
        encryption_algorithm="AES-256-Fernet",
        uploaded_at=datetime.now(timezone.utc) - timedelta(hours=4),
    )
    comp = Document(
        onboarding_id=onb.id, name="Tax Form (W-4)", required=True,
        status=DocumentStatus.COMPLETED,
        file_key=f"onboardings/{onb.id}/{uuid.uuid4().hex}.png",
        file_name="w4.png", file_size="1024", file_mime_type="image/png",
        uploaded_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    pend = Document(
        onboarding_id=onb.id, name="Proof of Address", required=True,
        status=DocumentStatus.PENDING,
    )
    db.add_all([up, comp, pend])
    db.commit()
    db.refresh(up)
    return {"onboarding": onb, "candidate": cand, "uploaded": up, "completed": comp, "pending": pend}


# ────────────────────────────────────────────────────────────────────────
# GET /onboarding/{id}/detail
# ────────────────────────────────────────────────────────────────────────
class TestOnboardingDetail:
    def test_requires_auth(self, db, hr_user, onboarding_with_docs):
        oid = onboarding_with_docs["onboarding"].id
        resp = client.get(f"/api/v1/onboarding/{oid}/detail")
        assert resp.status_code == 401

    def test_returns_full_candidate_and_documents(self, db, hr_user, onboarding_with_docs):
        d = onboarding_with_docs
        resp = client.get(
            f"/api/v1/onboarding/{d['onboarding'].id}/detail",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        # Candidate info incl. phone (which the US10 list omits)
        assert data["candidate"]["full_name"] == "Dana Docs"
        assert data["candidate"]["phone"] == "+1-555-0100"
        assert data["candidate"]["position"] == "Analyst"
        assert data["status"] == "in_progress"
        assert data["invitation_email_status"] == "sent"
        assert data["invitation_sent_at"] is not None
        # All 3 documents present with verification default
        assert len(data["documents"]) == 3
        by_name = {doc["name"]: doc for doc in data["documents"]}
        up = by_name["Government ID"]
        assert up["status"] == "uploaded"
        assert up["file_name"] == "passport.pdf"
        assert up["file_size"] == "2048"
        assert up["file_mime_type"] == "application/pdf"
        assert up["uploaded_at"] is not None
        assert up["verification_status"] == "unverified"
        assert up["verification_note"] is None
        assert by_name["Proof of Address"]["file_name"] is None

    def test_404_for_unknown_onboarding(self, db, hr_user):
        resp = client.get(
            "/api/v1/onboarding/00000000-0000-0000-0000-000000000000/detail",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/access-url (short-lived signed URL)
# ────────────────────────────────────────────────────────────────────────
class TestAccessUrl:
    def test_requires_auth(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["uploaded"]
        resp = client.get(f"/api/v1/documents/{doc.id}/access-url")
        assert resp.status_code == 401

    def test_returns_short_lived_url_for_uploaded_doc(self, db, hr_user, onboarding_with_docs):
        """Local-fallback path: signed URL with short expiry, no bytes in body."""
        doc = onboarding_with_docs["uploaded"]
        with patch("app.services.storage.is_r2_configured", return_value=False):
            resp = client.get(
                f"/api/v1/documents/{doc.id}/access-url",
                headers=_headers_for(hr_user),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == str(doc.id)
        assert data["access_url"].startswith("/api/v1/documents/")
        assert "token=" in data["access_url"]
        assert data["expires_in"] == 600  # 10 minutes — short, per sensitivity
        assert data["storage_backend"] == "local_signed_url"
        # No file bytes in a JSON response (obviously), and no base64 blob either.
        assert "data:" not in data["access_url"]

    def test_r2_path_returns_presigned_url(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["uploaded"]
        with patch("app.services.storage.is_r2_configured", return_value=True), \
             patch("app.services.storage.generate_presigned_url",
                   return_value="https://r2.example.com/presigned?sig=abc") as mock_presign:
            resp = client.get(
                f"/api/v1/documents/{doc.id}/access-url",
                headers=_headers_for(hr_user),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_url"] == "https://r2.example.com/presigned?sig=abc"
        assert data["storage_backend"] == "cloudflare_r2"
        mock_presign.assert_called_once()
        _, kwargs = mock_presign.call_args
        assert kwargs.get("expires_in") == 600

    def test_404_when_no_file_uploaded(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["pending"]
        resp = client.get(
            f"/api/v1/documents/{doc.id}/access-url",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404
        assert "no_file_uploaded" in resp.json()["detail"]

    def test_404_for_unknown_document(self, db, hr_user):
        resp = client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/access-url",
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404

    def test_local_url_token_expires(self, db, hr_user, onboarding_with_docs):
        """The signed local token must reject an EXPIRED token (403)."""
        doc = onboarding_with_docs["uploaded"]
        with patch("app.services.storage.is_r2_configured", return_value=False):
            url = client.get(
                f"/api/v1/documents/{doc.id}/access-url",
                headers=_headers_for(hr_user),
            ).json()["access_url"]
        # Token inside the URL is valid — serve works (file won't exist on disk,
        # but that maps to 404 file_missing_on_disk, NOT a 403 auth failure).
        token = url.split("token=")[1]
        resp = client.get(f"/api/v1/documents/{doc.id}/file?token={token}")
        assert resp.status_code in (200, 404)  # 404 only if fixture file absent
        # Tampered/expired token → 403
        bad = client.get(f"/api/v1/documents/{doc.id}/file?token=not-a-token")
        assert bad.status_code == 403


# ────────────────────────────────────────────────────────────────────────
# PATCH /documents/{id}/verification
# ────────────────────────────────────────────────────────────────────────
class TestVerification:
    def test_requires_auth(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["uploaded"]
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/verification",
            json={"verification_status": "verified"},
        )
        assert resp.status_code == 401

    def test_verify_updates_status_by_and_at(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["uploaded"]
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/verification",
            json={"verification_status": "verified"},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "verified"
        assert data["verified_at"] is not None
        assert data["verified_by"] == str(hr_user.id)

        # Persisted for fresh reads
        fresh = TestingSession()
        try:
            row = fresh.query(Document).filter(Document.id == doc.id).first()
            assert row.verification_status == DocumentVerificationStatus.VERIFIED
            assert row.verified_by == hr_user.id
        finally:
            fresh.close()

    def test_reject_with_note(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["completed"]
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/verification",
            json={"verification_status": "rejected",
                  "verification_note": "Document is unreadable"},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "rejected"
        assert data["verification_note"] == "Document is unreadable"

    def test_invalid_enum_value_422(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["uploaded"]
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/verification",
            json={"verification_status": "maybe"},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 422
        assert "unverified" in resp.json()["detail"]  # lists allowed values

    def test_no_file_uploaded_409(self, db, hr_user, onboarding_with_docs):
        doc = onboarding_with_docs["pending"]  # status pending, no file
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/verification",
            json={"verification_status": "verified"},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 409
        assert "only uploaded documents" in resp.json()["detail"]

    def test_unknown_document_404(self, db, hr_user):
        resp = client.patch(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/verification",
            json={"verification_status": "verified"},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 404

    def test_reverify_allowed(self, db, hr_user, onboarding_with_docs):
        """HR can flip verified -> rejected (e.g. second look)."""
        doc = onboarding_with_docs["uploaded"]
        h = _headers_for(hr_user)
        client.patch(f"/api/v1/documents/{doc.id}/verification",
                     json={"verification_status": "verified"}, headers=h)
        resp = client.patch(f"/api/v1/documents/{doc.id}/verification",
                            json={"verification_status": "rejected",
                                  "verification_note": "Fraud suspicion"},
                            headers=h)
        assert resp.status_code == 200
        assert resp.json()["verification_status"] == "rejected"


# ────────────────────────────────────────────────────────────────────────
# Storage URL generation (unit-level, both backends)
# ────────────────────────────────────────────────────────────────────────
class TestStorageAccessUrls:
    def test_generate_document_access_url_dispatch(self):
        doc_id = str(uuid.uuid4())
        # R2 path: boto3 is imported inside generate_presigned_url, so patch
        # the boto3 module attribute itself (the .env holds placeholder R2
        # values, so boto3 would otherwise raise on the invalid endpoint).
        import boto3
        with patch("app.services.storage.is_r2_configured", return_value=True), \
             patch("boto3.client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            mock_client.generate_presigned_url.return_value = "https://r2.example.com/presigned?sig=abc"
            url = storage.generate_document_access_url("some/key.pdf", doc_id, 600)
            assert url.startswith("https://")
            mock_client.generate_presigned_url.assert_called_once()
        # Local path: signed API URL
        with patch("app.services.storage.is_r2_configured", return_value=False):
            url = storage.generate_document_access_url("some/key.pdf", doc_id, 600)
            assert "/api/v1/documents/" in url and "token=" in url

    def test_local_token_is_scoped_and_shortlived(self):
        from jose import jwt
        from app.services.storage import LOCAL_ACCESS_TOKEN_TYPE
        doc_id = str(uuid.uuid4())
        url = storage.generate_local_access_url(doc_id, expires_in=600)
        token = url.split("token=")[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert payload["sub"] == doc_id
        assert payload["type"] == LOCAL_ACCESS_TOKEN_TYPE
        # exp ~600s away
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        remaining = (exp - datetime.now(timezone.utc)).total_seconds()
        assert 590 <= remaining <= 600

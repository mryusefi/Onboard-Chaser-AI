"""Tests for the maintenance pass Part C — fully custom required documents.

Covers: document_type enum on Document + create schemas, type->formats
derivation, explicit accepted_formats still win, sanity validation (1..20),
invalid type -> 422, defaults carry types, and document_type surfacing on
the portal and US11 detail endpoints.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, pwd_context
from app.models.models import Document, DocumentType, User
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"partc_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Part C HR",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _candidate_payload(email=None):
    return {
        "email": email or f"c_{uuid.uuid4().hex[:8]}@example.com",
        "full_name": "Custom Docs",
        "phone": "",
        "position": "QA",
    }


CUSTOM_DOCS = [
    {"name": "Photo ID", "document_type": "image"},
    {"name": "NDA", "document_type": "pdf_document"},
    {"name": "Portfolio", "document_type": "file"},
    {"name": "Cert Scan", "document_type": "image", "accepted_formats": "PNG"},
    {"name": "Legacy Doc"},  # no type at all -> classic default
]


class TestCustomDocumentTypes:
    def test_create_full_custom_list_with_types(self, db, hr_user):
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload(), "required_documents": CUSTOM_DOCS},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200, resp.text
        docs = {d["name"]: d for d in resp.json()["documents"]}
        assert len(docs) == 5  # fully arbitrary list, replaces defaults
        # type-derived formats when omitted
        assert docs["Photo ID"]["document_type"] == "image"
        assert docs["Photo ID"]["accepted_formats"] == "JPG, PNG, GIF"
        assert docs["NDA"]["accepted_formats"] == "PDF"
        assert docs["Portfolio"]["accepted_formats"] == "PDF, JPG, PNG, GIF"
        # explicit accepted_formats win over the type default
        assert docs["Cert Scan"]["accepted_formats"] == "PNG"
        # no type at all -> None + classic default formats
        assert docs["Legacy Doc"]["document_type"] is None
        assert docs["Legacy Doc"]["accepted_formats"] == "PDF, JPG, PNG"

    def test_invalid_document_type_422(self, db, hr_user):
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload(),
                  "required_documents": [{"name": "X", "document_type": "text_input"}]},
            headers=_headers_for(hr_user),
        )
        # text_input deliberately NOT implemented (needs follow-up story)
        assert resp.status_code == 422
        assert "image, pdf_document, file" in resp.json()["detail"]

    def test_more_than_max_documents_422(self, db, hr_user):
        docs = [{"name": f"Doc {i}", "document_type": "file"} for i in range(21)]
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload(), "required_documents": docs},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 422
        assert "20" in resp.json()["detail"]

    def test_exactly_max_documents_allowed(self, db, hr_user):
        docs = [{"name": f"Doc {i}", "document_type": "image"} for i in range(20)]
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload(), "required_documents": docs},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        assert len(resp.json()["documents"]) == 20

    def test_defaults_carry_document_types(self, db, hr_user):
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload()},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200
        docs = {d["name"]: d for d in resp.json()["documents"]}
        assert docs["Tax Form (W-4)"]["document_type"] == "pdf_document"
        assert docs["Government ID"]["document_type"] == "file"

    def test_separate_create_endpoint_supports_types(self, db, hr_user):
        # candidate first, then POST /onboarding/{candidate_id} with custom list.
        # Note: OnboardingCreate requires candidate_id in the body too (US06 shape).
        cand = client.post("/api/v1/candidates/", json={
            "email": f"sep_{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Sep", "phone": None, "position": None,
        }, headers=_headers_for(hr_user))
        assert cand.status_code == 200
        cid = cand.json()["id"]
        resp = client.post(
            f"/api/v1/onboarding/{cid}",
            json={"candidate_id": cid,
                  "required_documents": [{"name": "Badge photo", "document_type": "image"}]},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200, resp.text
        cand2 = client.post("/api/v1/candidates/", json={
            "email": f"sep2_{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Sep2", "phone": None, "position": None,
        }, headers=_headers_for(hr_user))
        cid2 = cand2.json()["id"]
        bad2 = client.post(
            f"/api/v1/onboarding/{cid2}",
            json={"candidate_id": cid2,
                  "required_documents": [{"name": "Y", "document_type": "nope"}]},
            headers=_headers_for(hr_user),
        )
        assert bad2.status_code == 422

    def test_detail_endpoint_exposes_document_type(self, db, hr_user):
        created = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": _candidate_payload(),
                  "required_documents": [{"name": "Scan", "document_type": "image"}]},
            headers=_headers_for(hr_user),
        ).json()
        oid = created["onboarding"]["id"]
        resp = client.get(f"/api/v1/onboarding/{oid}/detail", headers=_headers_for(hr_user))
        assert resp.status_code == 200
        assert resp.json()["documents"][0]["document_type"] == "image"

    def test_enum_values_stable_contract(self):
        # Contract with the frontend dropdown — renaming breaks the UI.
        assert [t.value for t in DocumentType] == ["image", "pdf_document", "file"]

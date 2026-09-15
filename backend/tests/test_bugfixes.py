"""Tests for the maintenance-pass bugfixes (Bugs 1–4 from manual testing).

Two root causes were fixed:

A. Schema drift — Base.metadata.create_all() never ALTERs existing tables,
   so a long-lived Postgres dev volume was missing US07/US11 columns
   (onboardings.invitation_*, documents.verification_*) and every SELECT
   referencing them raised UndefinedColumn -> raw HTTP 500. Fixed by
   app/core/schema_bootstrap.reconcile_additive_schema(), called in the app
   lifespan. Tests below simulate a drifted DB against the bootstrap
   function directly (SQLite in-memory: create a subset of tables/columns,
   run reconcile, assert the columns exist + defaults were backfilled).

B. Partial-failure orphans — create_full_onboarding committed the candidate
   first, so a later failure left an orphan (retries then hit a confusing
   409 "Candidate already exists" although the first attempt 500'd). The flow
   is now one transaction with rollback; a raced IntegrityError maps to a
   clean 409. Tests assert: success on a brand-new email; 409 (not 500) on
   the duplicate; and NO orphan candidate after a mid-flow failure.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base
from app.core.schema_bootstrap import reconcile_additive_schema
from app.core.security import create_access_token, pwd_context
from app.models.models import (
    Candidate,
    Document,
    InvitationEmailStatus,
    Onboarding,
    User,
)
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"bugfix_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Bugfix HR",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────
# A. Schema reconciliation (root cause of Bug 1/3/4's raw 500s)
# ─────────────────────────────────────────────────────────────────────────
class TestSchemaReconcile:
    def _drifted_engine(self):
        """In-memory SQLite with OLD table shapes (pre-US07/pre-US11)."""
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with engine.connect() as conn:
            # onboardings WITHOUT the US07 invitation_* columns
            conn.execute(text("""
                CREATE TABLE onboardings (
                    id CHAR(32) PRIMARY KEY,
                    candidate_id CHAR(32),
                    status VARCHAR(20),
                    magic_token TEXT,
                    token_expires_at DATETIME,
                    is_token_used BOOLEAN,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME
                )
            """))
            # documents WITHOUT the US11 verification_* columns
            conn.execute(text("""
                CREATE TABLE documents (
                    id CHAR(32) PRIMARY KEY,
                    onboarding_id CHAR(32),
                    name VARCHAR(255),
                    required BOOLEAN,
                    status VARCHAR(20),
                    created_at DATETIME
                )
            """))
            # one existing row per table (valid UUID strings — the model uses
            # UUID(as_uuid=True)), so the backfill is observable
            conn.execute(text(
                "INSERT INTO onboardings (id, status) VALUES "
                "(:ob_id, 'PENDING')"
            ), {"ob_id": self.OLD_ONBOARDING_ID})
            conn.execute(text(
                "INSERT INTO documents (id, name, status, onboarding_id) VALUES "
                "(:doc_id, 'ID', 'PENDING', :ob_id)"
            ), {"doc_id": self.OLD_DOCUMENT_ID, "ob_id": self.OLD_ONBOARDING_ID})
            conn.commit()
        return engine

    OLD_ONBOARDING_ID = str(uuid.uuid4())
    OLD_DOCUMENT_ID = str(uuid.uuid4())

    def test_reconcile_adds_missing_columns(self):
        engine = self._drifted_engine()
        actions = reconcile_additive_schema(engine, Base)
        cols_ob = {c["name"] for c in inspect(engine).get_columns("onboardings")}
        cols_doc = {c["name"] for c in inspect(engine).get_columns("documents")}
        assert {"invitation_sent_at", "invitation_email_status",
                "invitation_last_error"} <= cols_ob
        assert {"verification_status", "verification_note", "verified_at",
                "verified_by"} <= cols_doc
        assert "onboardings.invitation_sent_at" in actions

    def test_reconcile_backfills_enum_defaults_by_name(self):
        # SQLAlchemy's Enum stores the member NAME on disk; the backfill must
        # match, otherwise ORM loads would fail on old rows.
        engine = self._drifted_engine()
        reconcile_additive_schema(engine, Base)
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT invitation_email_status FROM onboardings WHERE id=:i"
            ), {"i": self.OLD_ONBOARDING_ID}).first()
            doc_row = conn.execute(text(
                "SELECT verification_status FROM documents WHERE id=:i"
            ), {"i": self.OLD_DOCUMENT_ID}).first()
        assert row[0] == InvitationEmailStatus.NOT_SENT.name  # 'NOT_SENT'
        assert doc_row[0] == "UNVERIFIED"

    def test_reconcile_is_idempotent(self):
        engine = self._drifted_engine()
        first = reconcile_additive_schema(engine, Base)
        second = reconcile_additive_schema(engine, Base)
        assert len(first) > 0
        assert second == []  # nothing left to add

    def test_full_model_select_after_reconcile(self):
        """The exact failing query shape (US10 list selects invitation_*)."""
        engine = self._drifted_engine()
        # Before: a model SELECT touching the missing column raises.
        Session = sessionmaker(bind=engine)
        s = Session()
        with pytest.raises(Exception):
            s.query(Onboarding).all()
        s.close()
        # After reconcile: same query works and returns the old row.
        reconcile_additive_schema(engine, Base)
        s2 = Session()
        try:
            rows = s2.query(Onboarding).all()
            assert len(rows) == 1
            assert rows[0].invitation_email_status == InvitationEmailStatus.NOT_SENT
        finally:
            s2.close()


# ─────────────────────────────────────────────────────────────────────────
# B. create-full atomicity + clean 409s (Bugs 1 & 3)
# ─────────────────────────────────────────────────────────────────────────
class TestCreateFullAtomicity:
    def test_new_email_succeeds_200(self, db, hr_user):
        email = f"fresh_{uuid.uuid4().hex[:6]}@example.com"
        resp = client.post(
            "/api/v1/onboarding/create-full",
            json={"candidate": {"email": email, "full_name": "Fresh User",
                                 "phone": "", "position": "Dev"}},
            headers=_headers_for(hr_user),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["candidate"]["email"] == email
        assert len(data["documents"]) == 4  # defaults seeded

    def test_duplicate_email_409_immediately(self, db, hr_user):
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        payload = {"candidate": {"email": email, "full_name": "Dup", "position": "Dev"}}
        r1 = client.post("/api/v1/onboarding/create-full", json=payload,
                         headers=_headers_for(hr_user))
        assert r1.status_code == 200
        r2 = client.post("/api/v1/onboarding/create-full", json=payload,
                         headers=_headers_for(hr_user))
        assert r2.status_code == 409
        assert r2.json()["detail"] == "Candidate already exists"

    def test_midflow_failure_rolls_back_no_orphan_candidate(self, db, hr_user, monkeypatch):
        """
        Reproduce the orphan mechanism: candidate row flushed (step 1), then a
        failure during onboarding/doc seeding (step 2) must roll EVERYTHING
        back — afterwards the email must be free again and create-full on the
        same email must succeed, not return a stale 'already exists' 409.
        """
        import app.services.onboarding_service as svc

        email = f"orphan_{uuid.uuid4().hex[:6]}@example.com"
        payload = {"candidate": {"email": email, "full_name": "Orphan",
                                  "position": "Analyst"}}

        original = svc.create_onboarding_for_candidate

        def explode(*args, **kwargs):
            raise ValueError("simulated seed failure")

        monkeypatch.setattr(svc, "create_onboarding_for_candidate", explode)
        resp = client.post("/api/v1/onboarding/create-full", json=payload,
                           headers=_headers_for(hr_user))
        assert resp.status_code == 400  # mapped ValueError, not a 500
        monkeypatch.undo()

        # The candidate must NOT exist (transaction was rolled back)…
        fresh = TestingSession()
        try:
            assert fresh.query(Candidate).filter(Candidate.email == email).first() is None
        finally:
            fresh.close()

        # …and retrying with the same email must succeed cleanly (200).
        retry = client.post("/api/v1/onboarding/create-full", json=payload,
                            headers=_headers_for(hr_user))
        assert retry.status_code == 200, retry.text
        assert retry.json()["candidate"]["email"] == email

    def test_candidates_endpoint_duplicate_still_409(self, db, hr_user):
        email = f"cand_{uuid.uuid4().hex[:6]}@example.com"
        body = {"email": email, "full_name": "C", "phone": None, "position": None}
        r1 = client.post("/api/v1/candidates/", json=body, headers=_headers_for(hr_user))
        assert r1.status_code == 201 or r1.status_code == 200
        r2 = client.post("/api/v1/candidates/", json=body, headers=_headers_for(hr_user))
        assert r2.status_code == 409

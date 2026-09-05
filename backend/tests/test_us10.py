"""Tests for US10 — HR dashboard (onboarding list endpoint)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, pwd_context
from app.models.models import (
    Candidate,
    Onboarding,
    OnboardingStatus,
    Document,
    DocumentStatus,
    ReminderLog,
    ReminderStatus,
    InvitationEmailStatus,
    User,
)
from tests.conftest import TestingSession

client = TestClient(app)


def _headers_for(user):
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id), 'email': user.email})}"
    }


def _make_candidate(db, hr_user, *, name="Jane Doe", email=None, position="Engineer"):
    cand = Candidate(
        email=email or f"{name.lower().replace(' ', '.')}_{uuid.uuid4().hex[:6]}@test.com",
        full_name=name,
        position=position,
        created_by=hr_user.id,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def _make_onboarding(
    db, hr_user, candidate=None, *,
    status=OnboardingStatus.PENDING,
    invited_hours_ago=None,
    expires_in_hours=None,
    invitation_status=InvitationEmailStatus.NOT_SENT,
    docs=None,  # list of (name, DocumentStatus)
):
    """Onboarding with explicit timing/invitation control for rule tests.
    By default: no invitation, no token, one pending document."""
    cand = candidate or _make_candidate(db, hr_user)
    now = datetime.now(timezone.utc)
    onb = Onboarding(
        candidate_id=cand.id,
        status=status,
        invitation_email_status=invitation_status,
        invitation_sent_at=now - timedelta(hours=invited_hours_ago) if invited_hours_ago is not None else None,
        token_expires_at=now + timedelta(hours=expires_in_hours) if expires_in_hours is not None else None,
    )
    db.add(onb)
    db.commit()
    db.refresh(onb)
    for name, doc_status in (docs or [("Government ID", DocumentStatus.PENDING)]):
        db.add(Document(onboarding_id=onb.id, name=name, status=doc_status))
    db.commit()
    db.refresh(onb)
    return onb


@pytest.fixture
def hr_user(db):
    user = User(
        email=f"hr10_{uuid.uuid4().hex[:6]}@test.com",
        full_name="HR Ten",
        hashed_password=pwd_context.hash("password123"),
        is_hr=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ────────────────────────────────────────────────────────────────────────
# Basic list behavior
# ────────────────────────────────────────────────────────────────────────
class TestListBasics:
    def test_requires_auth(self, db, hr_user):
        resp = client.get("/api/v1/onboarding/")
        assert resp.status_code == 401

    def test_empty_state(self, db, hr_user):
        """No onboardings yet -> empty list with metadata, not an error."""
        resp = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_lists_all_with_candidate_and_counts(self, db, hr_user):
        cand = _make_candidate(db, hr_user, name="Alice Smith", email="alice@x.com",
                               position="Designer")
        onb = _make_onboarding(
            db, hr_user, candidate=cand,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=10,
            docs=[
                ("ID", DocumentStatus.UPLOADED),
                ("W-4", DocumentStatus.PENDING),
                ("Offer", DocumentStatus.PENDING),
            ],
        )
        resp = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["onboarding_id"] == str(onb.id)
        assert item["candidate"]["full_name"] == "Alice Smith"
        assert item["candidate"]["email"] == "alice@x.com"
        assert item["candidate"]["position"] == "Designer"
        assert item["status"] == "in_progress"
        assert item["completed_documents"] == 1
        assert item["total_documents"] == 3
        assert item["completion_percentage"] == 33  # round(1/3*100)
        assert item["invitation_email_status"] == "sent"
        assert item["started_at"] is None
        assert item["completed_at"] is None

    def test_completed_onboarding_counts_all_docs(self, db, hr_user):
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.COMPLETED,
            invitation_status=InvitationEmailStatus.SENT,
            docs=[
                ("ID", DocumentStatus.COMPLETED),
                ("W-4", DocumentStatus.UPLOADED),
            ],
        )
        data = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()
        item = data["items"][0]
        assert item["completion_percentage"] == 100
        assert item["needs_attention"] is False


# ────────────────────────────────────────────────────────────────────────
# Filtering, search, pagination
# ────────────────────────────────────────────────────────────────────────
class TestFiltersAndPagination:
    @pytest.fixture
    def mixed_data(self, db, hr_user):
        p = _make_onboarding(db, hr_user, status=OnboardingStatus.PENDING)
        ip = _make_onboarding(db, hr_user, status=OnboardingStatus.IN_PROGRESS,
                              invitation_status=InvitationEmailStatus.SENT,
                              invited_hours_ago=1)
        c = _make_onboarding(db, hr_user, status=OnboardingStatus.COMPLETED,
                             invitation_status=InvitationEmailStatus.SENT,
                             docs=[("ID", DocumentStatus.COMPLETED)])
        return p, ip, c

    def test_filter_by_status(self, db, hr_user, mixed_data):
        p, ip, c = mixed_data
        resp = client.get("/api/v1/onboarding/?status=completed",
                          headers=_headers_for(hr_user))
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "completed"

    def test_invalid_status_rejected(self, db, hr_user):
        resp = client.get("/api/v1/onboarding/?status=bogus",
                          headers=_headers_for(hr_user))
        assert resp.status_code == 422
        assert "pending" in resp.json()["detail"]

    def test_search_by_name_and_email(self, db, hr_user):
        alice = _make_candidate(db, hr_user, name="Alice Wonder", email="aw@x.com")
        bob = _make_candidate(db, hr_user, name="Bob Builder", email="bob@y.com")
        _make_onboarding(db, hr_user, candidate=alice)
        _make_onboarding(db, hr_user, candidate=bob)

        by_name = client.get("/api/v1/onboarding/?search=wonder",
                             headers=_headers_for(hr_user)).json()
        assert by_name["total"] == 1
        assert by_name["items"][0]["candidate"]["full_name"] == "Alice Wonder"

        by_email = client.get("/api/v1/onboarding/?search=bob@y",
                              headers=_headers_for(hr_user)).json()
        assert by_email["total"] == 1
        assert by_email["items"][0]["candidate"]["email"] == "bob@y.com"

    def test_search_partial_substring_case_insensitive(self, db, hr_user):
        cand = _make_candidate(db, hr_user, name="Charlie Chaplin")
        _make_onboarding(db, hr_user, candidate=cand)
        resp = client.get("/api/v1/onboarding/?search=HARLIE",
                          headers=_headers_for(hr_user))
        assert resp.json()["total"] == 1

    def test_pagination_metadata_and_slices(self, db, hr_user):
        for i in range(5):
            _make_onboarding(db, hr_user)
        resp = client.get("/api/v1/onboarding/?page=2&page_size=2",
                          headers=_headers_for(hr_user))
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["items"]) == 2  # items 3-4

        # Last (partial) page
        resp3 = client.get("/api/v1/onboarding/?page=3&page_size=2",
                           headers=_headers_for(hr_user))
        data3 = resp3.json()
        assert len(data3["items"]) == 1
        assert data3["page"] == 3

    def test_page_beyond_total_returns_empty(self, db, hr_user):
        _make_onboarding(db, hr_user)
        data = client.get("/api/v1/onboarding/?page=9&page_size=20",
                          headers=_headers_for(hr_user)).json()
        assert data["items"] == []
        assert data["total"] == 1


# ────────────────────────────────────────────────────────────────────────
# needs_attention rule (representative scenarios)
# ────────────────────────────────────────────────────────────────────────
class TestNeedsAttentionRule:
    def test_expired_token_flagged(self, db, hr_user):
        """Expired link -> flagged even though invitation was sent."""
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=80,
            expires_in_hours=-1,  # expired 1h ago
        )
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is True

    def test_no_invitation_sent_flagged(self, db, hr_user):
        """Never invited -> flagged (stuck at step zero)."""
        _make_onboarding(db, hr_user)  # defaults: NOT_SENT, no token
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is True

    def test_stalled_zero_progress_flagged(self, db, hr_user):
        """Invited >24h ago, still 0% -> flagged even with a live token."""
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=48,
            expires_in_hours=24,  # token still live
        )
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is True

    def test_fresh_invitation_not_flagged(self, db, hr_user):
        """Recently invited, live token, 0% -> NOT flagged (within quiet period)."""
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
        )
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is False

    def test_partial_progress_not_flagged(self, db, hr_user):
        """Some progress + live token + recent -> healthy."""
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=48,
            expires_in_hours=24,
            docs=[("ID", DocumentStatus.UPLOADED), ("W-4", DocumentStatus.PENDING)],
        )
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is False
        assert items[0]["completion_percentage"] == 50

    def test_completed_never_flagged_even_with_expired_token(self, db, hr_user):
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.COMPLETED,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=200,
            expires_in_hours=-100,  # long expired
            docs=[("ID", DocumentStatus.COMPLETED)],
        )
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is False

    def test_last_reminder_failed_flagged(self, db, hr_user):
        """Recent invitation, live token, but the chaser FAILED -> flagged."""
        onb = _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
        )
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.FAILED,
            reminder_type="midway", reason="rate limit",
            sent_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        ))
        db.commit()
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is True

    def test_routine_skip_not_flagged(self, db, hr_user):
        """US08 scan writes routine 'no reminder due' skips hourly; those
        must NOT flood the dashboard. Cap-reached skips DO flag."""
        onb = _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
        )
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SKIPPED,
            reminder_type="midway", reason="no reminder due (before halfway point)",
            sent_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        ))
        db.commit()
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is False

    def test_cap_reached_skip_flagged(self, db, hr_user):
        """Cap-reached skip = candidate ignored all nudges -> flagged."""
        onb = _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
        )
        db.add(ReminderLog(
            onboarding_id=onb.id, status=ReminderStatus.SKIPPED,
            reminder_type="midway",
            reason="reminder cap reached (3/3 sent)",
            sent_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        ))
        db.commit()
        items = client.get("/api/v1/onboarding/", headers=_headers_for(hr_user)).json()["items"]
        assert items[0]["needs_attention"] is True

    def test_needs_attention_filter_true(self, db, hr_user):
        """needs_attention=true returns only flagged rows."""
        _make_onboarding(db, hr_user)  # flagged (no invitation)
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
            docs=[("ID", DocumentStatus.UPLOADED), ("W-4", DocumentStatus.UPLOADED)],
        )  # healthy (100% progress, live token)
        data = client.get("/api/v1/onboarding/?needs_attention=true",
                          headers=_headers_for(hr_user)).json()
        assert data["total"] == 1
        assert data["items"][0]["needs_attention"] is True

    def test_needs_attention_filter_false(self, db, hr_user):
        _make_onboarding(db, hr_user)  # flagged
        _make_onboarding(
            db, hr_user,
            status=OnboardingStatus.IN_PROGRESS,
            invitation_status=InvitationEmailStatus.SENT,
            invited_hours_ago=2,
            expires_in_hours=70,
            docs=[("ID", DocumentStatus.UPLOADED), ("W-4", DocumentStatus.UPLOADED)],
        )  # healthy
        data = client.get("/api/v1/onboarding/?needs_attention=false",
                          headers=_headers_for(hr_user)).json()
        assert data["total"] == 1
        assert data["items"][0]["needs_attention"] is False

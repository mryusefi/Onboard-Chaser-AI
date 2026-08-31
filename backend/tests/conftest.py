"""Shared test fixtures for all US test suites."""
import os
import uuid

os.environ["TESTING"] = "1"

import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.models import User, Candidate
from app.core.security import pwd_context


# Single shared in-memory engine for all test files
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _fresh_tables():
    """Drop and recreate all tables before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def hr_headers(client=None):
    """
    Register + login an HR user via the API and return auth headers (US06).

    Usage: pass as `headers=hr_headers` on HR-facing requests.
    """
    from fastapi.testclient import TestClient

    c = client or TestClient(app)
    email = "hr_admin@test.com"
    c.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "HR Admin", "password": "secret123"},
    )
    resp = c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_hr_headers() -> dict:
    """Non-fixture variant for module-level use inside other fixtures."""
    from fastapi.testclient import TestClient

    c = TestClient(app)
    email = f"hr_{uuid.uuid4().hex[:8]}@test.com"
    c.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "HR Admin", "password": "secret123"},
    )
    resp = c.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

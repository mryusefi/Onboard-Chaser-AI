"""Tests for the maintenance-pass auth fixes (Bug 2).

Root cause: Swagger UI's "Authorize" button posts application/x-www-form-
urlencoded to the declared tokenUrl (/api/v1/auth/login), but that endpoint
consumes a JSON body -> the token could never be obtained -> every HR
endpoint reported "Not authenticated" in Swagger.

Fix: POST /api/v1/auth/token (OAuth2PasswordRequestForm) + tokenUrl moved
there. /auth/login (JSON) is kept unchanged for the frontend login page.

NOTE on the fixture: the HR user is created through the API register
endpoint (same convention as conftest.hr_headers) — with the shared-
connection in-memory SQLite harness, API-hash -> API-verify is the proven
path; direct ORM-inserted hashed users are not reliably visible to the
request path.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

HR_EMAIL = "auth_test_hr@test.com"
HR_PASSWORD = "***"


@pytest.fixture
def hr_user():
    """Create the HR account through the API (proven pattern in the suite)."""
    from collections import namedtuple
    resp = client.post("/api/v1/auth/register", json={
        "email": HR_EMAIL, "full_name": "Auth HR", "password": HR_PASSWORD,
    })
    assert resp.status_code == 200, resp.text
    return namedtuple("HR", "email password")(HR_EMAIL, HR_PASSWORD)


class TestTokenEndpoint:
    def test_token_form_login_returns_bearer(self, hr_user):
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": hr_user.email, "password": "***"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]

    def test_token_form_login_wrong_password_401(self, hr_user):
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": hr_user.email, "password": hr_user.password + "-wrong"},
        )
        assert resp.status_code == 401

    def test_token_from_form_endpoint_unlocks_settings(self, hr_user):
        """The full Swagger Authorize flow: token via /auth/token -> HR
        endpoint accepts the Bearer header."""
        tok = client.post(
            "/api/v1/auth/token",
            data={"username": hr_user.email, "password": "***"},
        ).json()["access_token"]
        resp = client.get(
            "/api/v1/settings/reminders",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.status_code == 200
        assert "is_enabled" in resp.json()

    def test_openapi_tokenurl_points_at_form_endpoint(self):
        """Swagger's Authorize posts form data to the declared tokenUrl —
        it must point at /auth/token (form) not /auth/login (JSON)."""
        spec = client.get("/openapi.json").json()
        flows = spec["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]
        assert flows["password"]["tokenUrl"].endswith("/auth/token")

    def test_json_login_still_works_for_frontend(self, hr_user):
        """Back-compat: the frontend Login page keeps using the JSON
        /auth/login shape — it must not regress."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": hr_user.email, "password": "***"},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

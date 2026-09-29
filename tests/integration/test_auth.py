"""Accounts: sign-up, sign-in, sessions, Google linking, and that data needs a session."""
import pytest

from backend.routers import auth as auth_router
from pipeline.config import settings

CREDS = {"email": "Ada@Example.com", "password": "correct horse"}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_data_endpoints_require_a_session_but_health_does_not(anon_client):
    for path in ("/news", "/reports", "/sectors", "/stats", "/quotes?symbols=NVDA", "/candles/NVDA"):
        r = anon_client.get(path)
        assert r.status_code == 401, path
        assert r.headers["www-authenticate"] == "Bearer"
    assert anon_client.get("/news", headers=_bearer("not-a-real-token")).status_code == 401
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/auth/config").json() == {"google_client_id": None, "password": True, "signup": True}


def test_signup_login_me_logout(anon_client):
    r = anon_client.post("/auth/signup", json={**CREDS, "name": " Ada "})
    assert r.status_code == 201
    body = r.json()
    assert body["user"] == {"id": body["user"]["id"], "email": "ada@example.com", "name": "Ada", "has_password": True, "google": False}
    token = body["token"]
    assert anon_client.get("/news", headers=_bearer(token)).status_code == 200

    # Same email in any case is taken; weak passwords and bad emails are rejected.
    assert anon_client.post("/auth/signup", json={**CREDS, "email": "ADA@example.com"}).status_code == 409
    assert anon_client.post("/auth/signup", json={"email": "b@example.com", "password": "short"}).status_code == 422
    assert anon_client.post("/auth/signup", json={"email": "nope", "password": "long enough"}).status_code == 422

    login = anon_client.post("/auth/login", json={"email": " ADA@example.com ", "password": "correct horse"})
    assert login.status_code == 200 and login.json()["token"] != token
    assert anon_client.post("/auth/login", json={**CREDS, "password": "wrong"}).status_code == 401
    assert anon_client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}).status_code == 401

    assert anon_client.get("/auth/me", headers=_bearer(token)).json()["email"] == "ada@example.com"
    assert anon_client.post("/auth/logout", headers=_bearer(token)).status_code == 204
    assert anon_client.get("/auth/me", headers=_bearer(token)).status_code == 401
    # The other session is unaffected.
    assert anon_client.get("/auth/me", headers=_bearer(login.json()["token"])).status_code == 200


def test_login_is_throttled(anon_client):
    anon_client.post("/auth/signup", json=CREDS)
    codes = [anon_client.post("/auth/login", json={**CREDS, "password": "wrong"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_passwords_are_hashed(anon_client, db_session):
    from pipeline.db.models import User

    anon_client.post("/auth/signup", json=CREDS)
    stored = db_session.query(User).one().password_hash
    assert stored.startswith("scrypt$") and "correct horse" not in stored


@pytest.fixture
def google_enabled(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    claims = {"sub": "g-123", "email": "ada@example.com", "email_verified": True, "name": "Ada L."}
    monkeypatch.setattr(auth_router, "verify_google_credential", lambda credential: claims)
    return claims


def test_google_creates_then_links_accounts(anon_client, google_enabled):
    assert anon_client.get("/auth/config").json()["google_client_id"] == "test-client.apps.googleusercontent.com"
    first = anon_client.post("/auth/google", json={"credential": "x"}).json()
    assert first["user"]["google"] and not first["user"]["has_password"] and first["user"]["name"] == "Ada L."
    # Password sign-up for a Google-only email is refused (can't prove ownership that way).
    assert anon_client.post("/auth/signup", json=CREDS).status_code == 409
    again = anon_client.post("/auth/google", json={"credential": "x"}).json()
    assert again["user"]["id"] == first["user"]["id"]


def test_google_links_to_existing_password_account(anon_client, google_enabled):
    created = anon_client.post("/auth/signup", json=CREDS).json()["user"]
    linked = anon_client.post("/auth/google", json={"credential": "x"}).json()["user"]
    assert linked["id"] == created["id"] and linked["google"] and linked["has_password"]


def test_google_disabled_without_client_id(anon_client):
    assert anon_client.post("/auth/google", json={"credential": "x"}).status_code == 404

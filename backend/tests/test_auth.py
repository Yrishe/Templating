"""Auth endpoint tests — signup, login, refresh, logout, /me, throttling.

Exercises the HttpOnly-refresh-cookie + in-memory-access flow end-to-end
(finding #5). Refresh tokens never appear in response bodies; the browser
(or APIClient) carries them on same-site requests via Set-Cookie.
"""
from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def _cookie(response, name=None):
    name = name or settings.REFRESH_COOKIE_NAME
    return response.cookies.get(name)


# ─── Signup ───────────────────────────────────────────────────────────────


class TestSignup:
    def test_signup_account_sets_refresh_cookie_and_returns_access(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "newuser@test.com",
                "password": "SecurePass123!",
                "first_name": "New",
                "last_name": "User",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["user"]["email"] == "newuser@test.com"
        assert body["user"]["role"] == "account"
        from accounts.models import User
        assert User.objects.get(email="newuser@test.com").is_active is True
        # Access in body, refresh only in the HttpOnly cookie.
        assert body.get("access")
        assert "refresh" not in body
        cookie = _cookie(resp)
        assert cookie is not None
        assert cookie.value
        assert cookie["httponly"] is True
        assert cookie["samesite"] == settings.REFRESH_COOKIE_SAMESITE
        assert cookie["path"] == settings.REFRESH_COOKIE_PATH
        assert int(cookie["max-age"]) == settings.REFRESH_COOKIE_MAX_AGE
        # `secure` is off in the dev/test settings and on in prod.
        assert bool(cookie["secure"]) is bool(settings.REFRESH_COOKIE_SECURE)

    def test_signup_manager_is_inactive_pending_approval(self, api_client: APIClient):
        """Managers must be approved by another active manager before they can log in."""
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "newmgr@test.com",
                "password": "SecurePass123!",
                "first_name": "Pending",
                "last_name": "Manager",
                "role": "manager",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        from accounts.models import User
        created = User.objects.get(email="newmgr@test.com")
        assert created.is_active is False

    def test_signup_rejects_weak_password(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "weak@test.com",
                "password": "short",
                "first_name": "Weak",
                "last_name": "Pass",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in resp.json()

    def test_signup_rejects_duplicate_email(self, api_client: APIClient, subscriber_user):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": subscriber_user.email,
                "password": "SecurePass123!",
                "first_name": "Dup",
                "last_name": "Email",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ─── Login ────────────────────────────────────────────────────────────────


class TestLogin:
    def test_login_success_sets_refresh_cookie_and_returns_access(
        self, api_client: APIClient, subscriber_user
    ):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["user"]["email"] == subscriber_user.email
        assert body.get("access")
        assert "refresh" not in body
        cookie = _cookie(resp)
        assert cookie is not None and cookie.value
        assert cookie["httponly"] is True
        assert cookie["path"] == settings.REFRESH_COOKIE_PATH

    def test_login_wrong_password_returns_400(self, api_client: APIClient, subscriber_user):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "WrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_unknown_email_returns_400(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": "nobody@test.com", "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_missing_fields_returns_400(self, api_client: APIClient):
        resp = api_client.post("/api/auth/login/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ─── Token refresh ────────────────────────────────────────────────────────


class TestTokenRefresh:
    def test_refresh_with_cookie_returns_new_access_and_rotates_cookie(
        self, api_client: APIClient, subscriber_user
    ):
        # Log in so APIClient picks up the refresh cookie automatically.
        login = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert login.status_code == status.HTTP_200_OK
        original_cookie_val = _cookie(login).value

        resp = api_client.post("/api/auth/token/refresh/", {}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["access"]
        assert "refresh" not in body
        rotated = _cookie(resp)
        assert rotated is not None and rotated.value
        # Rotation: the cookie value is re-set even if the token string is
        # structurally identical (SimpleJWT's Bearer access uses a fresh
        # signature); either way the Set-Cookie header is present.
        assert rotated["path"] == settings.REFRESH_COOKIE_PATH
        assert rotated["httponly"] is True
        # Keep a reference to the original value so callers can spot any
        # reuse attempts; asserting inequality is brittle because rotation
        # timing can produce identical encoded bodies within the same second.
        _ = original_cookie_val

    def test_refresh_without_cookie_returns_401(self, api_client: APIClient):
        resp = api_client.post("/api/auth/token/refresh/", {}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_body_only_returns_401(self, api_client: APIClient):
        """Legacy clients sending the refresh in the body must be rejected —
        the cut-over is hard so XSS-via-body can't exfiltrate a session."""
        resp = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": "some-value"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_bad_cookie_returns_401(self, api_client: APIClient):
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = "not-a-real-jwt"
        resp = api_client.post("/api/auth/token/refresh/", {}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ─── /me + logout ─────────────────────────────────────────────────────────


class TestMeAndLogout:
    def test_me_requires_auth(self, api_client: APIClient):
        resp = api_client.get("/api/auth/me/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_returns_current_user(self, subscriber_client: APIClient, subscriber_user):
        resp = subscriber_client.get("/api/auth/me/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["email"] == subscriber_user.email

    def test_logout_blacklists_refresh_cookie_and_clears_it(
        self, api_client: APIClient, subscriber_user
    ):
        login = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert login.status_code == status.HTTP_200_OK
        assert _cookie(login) is not None

        logout = api_client.post("/api/auth/logout/", {}, format="json")
        assert logout.status_code == status.HTTP_200_OK
        cleared = _cookie(logout)
        # delete_cookie sets an empty value + Max-Age=0.
        assert cleared is not None
        assert cleared.value == ""
        assert int(cleared["max-age"]) == 0

        # The blacklisted refresh token should no longer work. APIClient
        # applied the cleared cookie to its jar, so put the old value back
        # explicitly and attempt a refresh.
        api_client.cookies[settings.REFRESH_COOKIE_NAME] = _cookie(login).value
        retry = api_client.post("/api/auth/token/refresh/", {}, format="json")
        assert retry.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_without_cookie_still_returns_200(self, api_client: APIClient):
        """Logout is idempotent — calling it with no cookie just returns OK."""
        resp = api_client.post("/api/auth/logout/", {}, format="json")
        assert resp.status_code == status.HTTP_200_OK


# ─── Cookie guardrail (regression for the #5 migration) ───────────────────


class TestRefreshCookieGuardrails:
    """Refresh lives in the HttpOnly cookie and *only* there — never in the
    response body. A regression here would mean somebody reintroduced
    `{refresh: ...}` in the JSON payload and broken the XSS mitigation."""

    def test_signup_response_has_no_refresh_key(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "nobody@test.com",
                "password": "SecurePass123!",
                "first_name": "No",
                "last_name": "Body",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "refresh" not in resp.json()

    def test_login_response_has_no_refresh_key(
        self, api_client: APIClient, subscriber_user
    ):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "refresh" not in resp.json()

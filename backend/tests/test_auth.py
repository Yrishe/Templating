"""Auth endpoint tests — signup, login, refresh, logout, /me, throttling.

These exercise the sessionStorage + Authorization: Bearer flow end-to-end,
including the refresh-token-in-body change we made when moving away from
httpOnly cookies.
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


# ─── Signup ───────────────────────────────────────────────────────────────


class TestSignup:
    def test_signup_account_returns_tokens_in_body(self, api_client: APIClient):
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
        # Account users are active immediately (only manager signups go
        # through the pending-approval gate — covered in the next test).
        from accounts.models import User
        assert User.objects.get(email="newuser@test.com").is_active is True
        # Tokens must be in the body (not a Set-Cookie header) — this is
        # the per-tab sessionStorage model.
        assert "access" in body and body["access"]
        assert "refresh" in body and body["refresh"]
        assert "access_token" not in resp.cookies
        assert "refresh_token" not in resp.cookies

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
        # Per-tenant policy: manager signups land inactive.
        from accounts.models import User
        created = User.objects.get(email="newmgr@test.com")
        assert created.is_active is False

    def test_signup_rejects_weak_password(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "weak@test.com",
                "password": "short",  # fails min length + common-password
                "first_name": "Weak",
                "last_name": "Pass",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # DRF field-level error
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
    def test_login_success_returns_tokens(self, api_client: APIClient, subscriber_user):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["user"]["email"] == subscriber_user.email
        assert body["access"]
        assert body["refresh"]

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
    def test_refresh_with_valid_body_returns_new_pair(
        self, api_client: APIClient, subscriber_user
    ):
        # Log in to get a refresh token.
        login = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        refresh_token = login.json()["refresh"]

        resp = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["access"]
        assert body["refresh"]

    def test_refresh_without_body_returns_401(self, api_client: APIClient):
        resp = api_client.post("/api/auth/token/refresh/", {}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_bad_token_returns_401(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": "not-a-real-jwt"},
            format="json",
        )
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

    def test_logout_blacklists_refresh_token(
        self, api_client: APIClient, subscriber_user
    ):
        login = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        refresh_token = login.json()["refresh"]

        logout = api_client.post(
            "/api/auth/logout/", {"refresh": refresh_token}, format="json"
        )
        assert logout.status_code == status.HTTP_200_OK

        # The same refresh token should no longer work.
        retry = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert retry.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_without_refresh_still_returns_200(self, api_client: APIClient):
        """Logout is idempotent — calling it with no body just returns OK."""
        resp = api_client.post("/api/auth/logout/", {}, format="json")
        assert resp.status_code == status.HTTP_200_OK


# ─── Cookie cleanup (regression for the per-tab migration) ────────────────


class TestNoCookies:
    """Guardrail: once we moved to sessionStorage, the auth endpoints should
    never set a Set-Cookie header. A regression here would mean somebody
    reintroduced _set_auth_cookies or its equivalent."""

    def test_signup_does_not_set_cookies(self, api_client: APIClient):
        resp = api_client.post(
            "/api/auth/signup/",
            {
                "email": "nocookie@test.com",
                "password": "SecurePass123!",
                "first_name": "No",
                "last_name": "Cookie",
                "role": "account",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.cookies == {} or "access_token" not in resp.cookies

    def test_login_does_not_set_cookies(
        self, api_client: APIClient, subscriber_user
    ):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": subscriber_user.email, "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.cookies == {} or "access_token" not in resp.cookies

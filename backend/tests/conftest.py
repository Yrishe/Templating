from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import Account, User
from projects.models import Project, ProjectMembership, Timeline


# ─── User + account fixtures ───────────────────────────────────────────────


@pytest.fixture
def manager_user(db) -> User:
    return User.objects.create_user(
        email="manager@test.com",
        password="TestPass123!",
        role=User.MANAGER,
        first_name="Alice",
        last_name="Manager",
    )


@pytest.fixture
def subscriber_user(db) -> User:
    return User.objects.create_user(
        email="subscriber@test.com",
        password="TestPass123!",
        role=User.SUBSCRIBER,
        first_name="Bob",
        last_name="Subscriber",
    )


@pytest.fixture
def second_account_user(db) -> User:
    """A second account-role user (useful for 'invited via add-member' tests)."""
    return User.objects.create_user(
        email="second-account@test.com",
        password="TestPass123!",
        role=User.ACCOUNT,
        first_name="Dana",
        last_name="Second",
    )


@pytest.fixture
def invited_user(db) -> User:
    return User.objects.create_user(
        email="invited@test.com",
        password="TestPass123!",
        role=User.INVITED_ACCOUNT,
        first_name="Carol",
        last_name="Invited",
    )


@pytest.fixture
def account(db, subscriber_user: User) -> Account:
    return Account.objects.create(
        subscriber=subscriber_user,
        name="Test Account Corp",
        email="contact@testaccount.com",
    )


@pytest.fixture
def project(db, account: Account, manager_user: User, subscriber_user: User) -> Project:
    """Project owned by subscriber_user (account), with manager_user also as a member."""
    proj = Project.objects.create(
        account=account,
        name="Test Project Alpha",
        description="Integration test project",
        generic_email="proj-alpha@test.com",
    )
    # Both the owner (subscriber) and a manager are members so we can
    # exercise manager/owner/non-member permission paths with the same
    # base project.
    ProjectMembership.objects.create(project=proj, user=subscriber_user)
    ProjectMembership.objects.create(project=proj, user=manager_user)
    Timeline.objects.get_or_create(project=proj)
    from chat.models import Chat
    Chat.objects.get_or_create(project=proj)
    return proj


# ─── API client fixtures ───────────────────────────────────────────────────
#
# Auth moved to per-tab sessionStorage + Authorization: Bearer. The test
# clients below force-authenticate using SimpleJWT so we exercise the same
# code path as the real app without round-tripping through login.


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF APIClient."""
    return APIClient()


def _auth_client(user: User) -> APIClient:
    """Return a client carrying an access token for `user`."""
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def manager_client(manager_user: User) -> APIClient:
    return _auth_client(manager_user)


@pytest.fixture
def subscriber_client(subscriber_user: User) -> APIClient:
    return _auth_client(subscriber_user)


@pytest.fixture
def invited_client(invited_user: User) -> APIClient:
    return _auth_client(invited_user)


# ─── File-upload fixtures ──────────────────────────────────────────────────


def _pdf_bytes(body: bytes = b"hello world") -> bytes:
    """Minimal valid-looking PDF for the magic-byte check.

    The validator in contracts/serializers.py only checks that the upload
    starts with `%PDF-`. A full pypdf round-trip isn't needed for the
    upload-path tests; only `test_extract_contract_text` would.
    """
    return b"%PDF-1.4\n" + body + b"\n%%EOF\n"


@pytest.fixture
def valid_pdf_upload() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "contract.pdf",
        _pdf_bytes(),
        content_type="application/pdf",
    )


@pytest.fixture
def not_a_pdf_upload() -> SimpleUploadedFile:
    """PNG magic bytes — for negative validation tests."""
    png_header = b"\x89PNG\r\n\x1a\n"
    return SimpleUploadedFile(
        "fake.pdf",  # wrong extension is fine; the validator sniffs bytes
        png_header + b"body",
        content_type="application/pdf",
    )


@pytest.fixture
def oversized_pdf_upload() -> SimpleUploadedFile:
    """A 'PDF' whose size exceeds the 10 MB cap.

    We don't actually allocate 10 MB — we use a `SimpleUploadedFile`
    and override the `size` attribute so the validator sees an oversized
    value without us paying the memory cost.
    """
    f = SimpleUploadedFile("big.pdf", _pdf_bytes(), content_type="application/pdf")
    # Attribute override — the validator only reads `.size`.
    f.size = 11 * 1024 * 1024  # 11 MB, over the 10 MB cap
    return f

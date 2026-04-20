from __future__ import annotations

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import Account, User
from contracts.models import Contract
from projects.models import Project, ProjectMembership, Timeline


# ─── Per-test state reset ──────────────────────────────────────────────────
#
# DRF's scoped throttles (auth, auth_refresh) persist their counters in
# the default cache backend (LocMemCache in dev). That cache is shared
# across the whole pytest session, so after ~10 signup/login calls the
# whole suite starts getting 429s — unrelated tests that happen to sign
# in a user hit the limit. Clearing the cache between tests isolates
# throttle state to the test that exercises it.


@pytest.fixture(autouse=True)
def _reset_cache():
    cache.clear()
    yield
    cache.clear()


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


def _pdf_bytes(_body: bytes = b"hello world") -> bytes:
    """Minimal *structurally-valid* PDF.

    The validator in contracts/serializers.py does a full pypdf round-trip
    (it was hardened to reject polyglot files — ZIP/HTML with a `%PDF-`
    prefix — so magic-byte alone isn't enough). The previous fixture
    produced bytes that passed the magic-byte check but failed
    `PdfReader(..., strict=False)` with "startxref not found", which
    silently broke every upload-path test.

    This blob is the smallest thing pypdf will parse: a catalog, an empty
    pages tree, a trailer, and an xref table. The `_body` arg is ignored —
    embedding arbitrary bytes in the middle breaks the byte-offset
    pointers in the xref table, and upload-path tests don't care about
    page content.
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"xref\n"
        b"0 3\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000055 00000 n \n"
        b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
        b"startxref\n"
        b"104\n"
        b"%%EOF\n"
    )


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
def contract_with_text(db, project: Project, manager_user: User) -> Contract:
    """A contract with extracted text content — used by AI pipeline tests."""
    contract, _ = Contract.objects.get_or_create(
        project=project,
        defaults={
            "title": "Test Contract Alpha",
            "content": (
                "SECTION 1 - SCOPE OF WORK\n"
                "The contractor shall deliver all materials within 30 days.\n\n"
                "SECTION 2 - PAYMENT TERMS\n"
                "Payment due within 15 days of invoice. Late penalty: 2% per month.\n\n"
                "SECTION 3 - DELAY CLAUSE\n"
                "Force majeure events extend deadlines by the duration of the event.\n"
                "Non-force-majeure delays incur liquidated damages of 0.5% per day.\n\n"
                "SECTION 4 - CHANGE ORDERS\n"
                "All scope changes must be approved in writing by both parties.\n"
                "Cost adjustments capped at 10% of original contract value.\n\n"
                "SECTION 5 - DISPUTE RESOLUTION\n"
                "Disputes shall be resolved through mediation, then binding arbitration."
            ),
            "status": Contract.ACTIVE,
            "created_by": manager_user,
        },
    )
    return contract


@pytest.fixture
def incoming_email_factory(db, project: Project):
    """Factory to create IncomingEmail instances with sequential message_ids."""
    from email_organiser.models import IncomingEmail
    from django.utils import timezone

    counter = [0]

    def _create(**kwargs):
        counter[0] += 1
        defaults = {
            "project": project,
            "sender_email": "supplier@example.com",
            "sender_name": "Acme Supplier",
            "subject": "Delivery delay notice",
            "body_plain": (
                "Dear Project Manager,\n\n"
                "We regret to inform you that the delivery of materials "
                "will be delayed by 2 weeks due to supply chain issues. "
                "This may affect the project timeline and incur additional costs.\n\n"
                "Regards,\nAcme Supplier"
            ),
            "message_id": f"<test-{counter[0]}@example.com>",
            "received_at": timezone.now(),
        }
        defaults.update(kwargs)
        return IncomingEmail.objects.create(**defaults)

    return _create


@pytest.fixture
def oversized_pdf_upload() -> SimpleUploadedFile:
    """A 'PDF' whose size exceeds the 10 MB cap.

    We need *real* bytes here. Trying to override `.size` on the
    client-side fixture doesn't work: DRF's test multipart parser reads
    the actual stream, constructs an `InMemoryUploadedFile` server-side
    with the real byte length, and the validator reads the real `.size`
    — not whatever we patched onto the client file. So we allocate 11 MB
    of padding once per test that needs it. Python GCs it at the end.
    """
    content = b"%PDF-1.4\n" + (b"x" * (11 * 1024 * 1024)) + b"\n%%EOF\n"
    return SimpleUploadedFile("big.pdf", content, content_type="application/pdf")

"""
Schema-level tests: verify tables, columns, constraints, and fixture seed data.

Run with:
    pytest tests/test_schema.py -v
"""
from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, connection

# ---------------------------------------------------------------------------
# 1. Table existence
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "accounts_user",
    "accounts_account",
    "projects_project",
    "projects_projectmembership",
    "projects_timeline",
    "projects_timelineevent",
    "contracts_contract",
    "contracts_contractrequest",
    "notifications_notification",
    "notifications_outboundemail",
    "chat_chat",
    "chat_message",
    "email_organiser_invitedaccount",
    "email_organiser_emailorganiser",
    "email_organiser_finalresponse",
    "email_organiser_recipient",
]


@pytest.mark.django_db
def test_all_tables_exist():
    with connection.cursor() as cursor:
        table_names = connection.introspection.get_table_names(cursor)
    for table in EXPECTED_TABLES:
        assert table in table_names, f"Missing table: {table}"


# ---------------------------------------------------------------------------
# 2. Required columns
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {
    "accounts_user": ["id", "email", "role", "password", "is_active", "date_joined"],
    "accounts_account": ["id", "subscriber_id", "name", "email", "created_at", "updated_at"],
    "projects_project": ["id", "account_id", "name", "description", "generic_email", "created_at", "updated_at"],
    "projects_projectmembership": ["id", "project_id", "user_id", "joined_at"],
    "projects_timeline": ["id", "project_id", "created_at", "updated_at"],
    "projects_timelineevent": ["id", "timeline_id", "title", "description", "start_date", "end_date", "status"],
    "contracts_contract": ["id", "project_id", "title", "content", "status", "created_by_id", "activated_at"],
    "contracts_contractrequest": ["id", "account_id", "project_id", "description", "status", "reviewed_at"],
    "notifications_notification": ["id", "project_id", "type", "is_read", "created_at"],
    "notifications_outboundemail": ["id", "to_address", "from_address", "subject", "body", "status"],
    "chat_chat": ["id", "project_id", "created_at"],
    "chat_message": ["id", "chat_id", "author_id", "content", "created_at", "updated_at"],
    "email_organiser_invitedaccount": ["id", "project_id", "user_id", "invited_at", "invited_by_id"],
    "email_organiser_emailorganiser": ["id", "project_id", "ai_context", "created_at", "updated_at"],
    "email_organiser_finalresponse": ["id", "email_organiser_id", "edited_by_id", "subject", "content", "status"],
    "email_organiser_recipient": ["id", "name", "email", "final_response_id"],
}


@pytest.mark.django_db
def test_required_columns_exist():
    with connection.cursor() as cursor:
        for table, required_cols in REQUIRED_COLUMNS.items():
            table_desc = connection.introspection.get_table_description(cursor, table)
            actual_cols = {col.name for col in table_desc}
            for col in required_cols:
                assert col in actual_cols, f"Missing column '{col}' in table '{table}'"


# ---------------------------------------------------------------------------
# 3. UNIQUE constraints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_email_uniqueness(subscriber_user):
    from accounts.models import User

    with pytest.raises(IntegrityError):
        User.objects.create_user(email=subscriber_user.email, password="Another1!")


@pytest.mark.django_db
def test_project_membership_unique_together(project, manager_user):
    from projects.models import ProjectMembership

    with pytest.raises(IntegrityError):
        ProjectMembership.objects.create(project=project, user=manager_user)


@pytest.mark.django_db
def test_recipient_unique_together(project, account):
    from contracts.models import Contract
    from email_organiser.models import EmailOrganiser, FinalResponse, Recipient

    contract = Contract.objects.create(project=project, title="T", content="C")
    organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
    fr = FinalResponse.objects.create(email_organiser=organiser, subject="S", content="C")
    Recipient.objects.create(name="John", email="john@test.com", final_response=fr)

    with pytest.raises(IntegrityError):
        Recipient.objects.create(name="John2", email="john@test.com", final_response=fr)


@pytest.mark.django_db
def test_invited_account_unique_together(project, invited_user, manager_user):
    from email_organiser.models import InvitedAccount

    InvitedAccount.objects.create(project=project, user=invited_user, invited_by=manager_user)

    with pytest.raises(IntegrityError):
        InvitedAccount.objects.create(project=project, user=invited_user, invited_by=manager_user)


# ---------------------------------------------------------------------------
# 4. NOT NULL constraints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_project_name_not_null(account):
    from django.db import IntegrityError as IE

    from projects.models import Project

    with pytest.raises((IE, Exception)):
        Project.objects.create(account=account, name=None)


@pytest.mark.django_db
def test_contract_title_not_null(project):
    from contracts.models import Contract

    with pytest.raises((IntegrityError, Exception)):
        Contract.objects.create(project=project, title=None, content="body")


@pytest.mark.django_db
def test_message_content_not_null(project, manager_user):
    from chat.models import Chat, Message

    chat, _ = Chat.objects.get_or_create(project=project)
    with pytest.raises((IntegrityError, Exception)):
        Message.objects.create(chat=chat, author=manager_user, content=None)


# ---------------------------------------------------------------------------
# 5. FK constraints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_project_account_fk_cascade(subscriber_user):
    from accounts.models import Account
    from projects.models import Project

    account = Account.objects.create(subscriber=subscriber_user, name="Temp", email="t@t.com")
    project = Project.objects.create(account=account, name="TempProj")
    account_pk = account.pk
    account.delete()
    assert not Project.objects.filter(pk=project.pk).exists()


@pytest.mark.django_db
def test_contract_project_fk_cascade(project):
    from contracts.models import Contract

    contract = Contract.objects.create(project=project, title="C", content="body")
    project.delete()
    assert not Contract.objects.filter(pk=contract.pk).exists()


@pytest.mark.django_db
def test_message_chat_fk_cascade(project, manager_user):
    from chat.models import Chat, Message

    chat, _ = Chat.objects.get_or_create(project=project)
    msg = Message.objects.create(chat=chat, author=manager_user, content="hello")
    chat.delete()
    assert not Message.objects.filter(pk=msg.pk).exists()


# ---------------------------------------------------------------------------
# 6. Migration smoke (django_db marker applies all migrations via pytest-django)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_migrations_applied():
    """If we reach here without errors all migrations have been applied."""
    with connection.cursor() as cursor:
        tables = connection.introspection.get_table_names(cursor)
    assert len(tables) > 0


# ---------------------------------------------------------------------------
# 7. Seed data integrity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_fixture_load_sanity(manager_user, subscriber_user, invited_user, account, project):
    """Verify that conftest fixtures produce valid DB objects."""
    from accounts.models import User

    assert User.objects.filter(role=User.MANAGER).count() >= 1
    assert User.objects.filter(role=User.SUBSCRIBER).count() >= 1
    assert User.objects.filter(role=User.INVITED_ACCOUNT).count() >= 1


@pytest.mark.django_db
def test_basic_crud_flow(manager_user, subscriber_user, account, project):
    """End-to-end object creation smoke test."""
    from contracts.models import Contract, ContractRequest
    from notifications.models import Notification

    # Contract
    contract = Contract.objects.create(
        project=project,
        title="Service Agreement",
        content="Terms and conditions...",
        created_by=manager_user,
    )
    assert contract.status == Contract.DRAFT

    # Contract request
    cr = ContractRequest.objects.create(
        account=account,
        project=project,
        description="Requesting a new contract.",
    )
    assert cr.status == ContractRequest.PENDING

    # Notification
    notif = Notification.objects.create(
        project=project,
        type=Notification.CONTRACT_REQUEST,
        triggered_by_contract_request=cr,
    )
    assert notif.is_read is False

    # Chat
    from chat.models import Chat, Message

    chat, _ = Chat.objects.get_or_create(project=project)
    msg = Message.objects.create(chat=chat, author=manager_user, content="Hello team!")
    assert msg.content == "Hello team!"

    # Email organiser
    from email_organiser.models import EmailOrganiser, FinalResponse, InvitedAccount, Recipient

    organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
    fr = FinalResponse.objects.create(
        email_organiser=organiser,
        subject="Welcome",
        content="Dear client, ...",
    )
    assert fr.status == FinalResponse.DRAFT

    recipient = Recipient.objects.create(name="Jane Doe", email="jane@example.com", final_response=fr)
    assert str(recipient) == "Jane Doe <jane@example.com>"

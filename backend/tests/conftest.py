from __future__ import annotations

import uuid

import pytest

from accounts.models import Account, User
from projects.models import Project, ProjectMembership, Timeline


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
def project(db, account: Account, manager_user: User) -> Project:
    proj = Project.objects.create(
        account=account,
        name="Test Project Alpha",
        description="Integration test project",
        generic_email="project@test.com",
    )
    ProjectMembership.objects.create(project=proj, user=manager_user)
    Timeline.objects.get_or_create(project=proj)
    from chat.models import Chat
    Chat.objects.get_or_create(project=proj)
    return proj

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager that uses email instead of username."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email address is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.MANAGER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    MANAGER = "manager"
    ACCOUNT = "account"
    SUBSCRIBER = "account"  # backward-compat alias
    INVITED_ACCOUNT = "invited_account"

    ROLE_CHOICES = [
        (MANAGER, "Manager"),
        (ACCOUNT, "Account"),
        (INVITED_ACCOUNT, "Invited Account"),
    ]

    # Override primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove username; use email as the unique identifier
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ACCOUNT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()  # type: ignore[assignment]

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return self.email


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="accounts",
        limit_choices_to={"role": User.ACCOUNT},
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["subscriber"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return self.name

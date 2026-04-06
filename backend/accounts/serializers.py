from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Account, User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirm password")

    class Meta:
        model = User
        fields = ["id", "email", "password", "password2", "role", "first_name", "last_name"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def validate_role(self, value):
        if value == User.INVITED_ACCOUNT:
            raise serializers.ValidationError(
                "Invited Accounts are added by a Manager, not via self-registration."
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        # Manager accounts require admin approval — disable until approved
        if user.role == User.MANAGER:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "first_name", "last_name", "date_joined", "last_login"]
        read_only_fields = ["id", "date_joined", "last_login"]


class AccountSerializer(serializers.ModelSerializer):
    subscriber = UserProfileSerializer(read_only=True)

    class Meta:
        model = Account
        fields = ["id", "subscriber", "name", "email", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "subscriber"]

    def create(self, validated_data):
        validated_data["subscriber"] = self.context["request"].user
        return super().create(validated_data)

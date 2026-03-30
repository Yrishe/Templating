from __future__ import annotations

from rest_framework import serializers

from .models import Contract, ContractRequest


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = [
            "id", "project", "title", "content", "status",
            "created_by", "created_at", "updated_at", "activated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "activated_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ContractRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequest
        fields = [
            "id", "account", "project", "description", "status",
            "created_at", "reviewed_at", "reviewed_by",
        ]
        read_only_fields = ["id", "status", "created_at", "reviewed_at", "reviewed_by"]

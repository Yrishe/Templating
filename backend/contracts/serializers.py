from __future__ import annotations

from rest_framework import serializers

from .models import Contract, ContractRequest


class ContractSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id", "project", "title", "file", "file_url", "content", "status",
            "created_by", "created_at", "updated_at", "activated_at",
        ]
        read_only_fields = ["id", "file_url", "created_by", "created_at", "updated_at", "activated_at"]

    def get_file_url(self, obj: Contract) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

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

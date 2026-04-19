from __future__ import annotations

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework import serializers

from .models import Contract, ContractRequest


# ─── Upload constraints ────────────────────────────────────────────────────
#
# Both file fields on this app (Contract.file and ContractRequest.attachment)
# accept only PDF. The 10 MB cap is a product decision — redlined contract
# PDFs are rarely larger. The browser-side `accept=".pdf"` filter is a UX
# hint; these validators are the real gate.

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
PDF_MAGIC = b"%PDF-"


def _validate_pdf_upload(file_obj, field_label: str):
    """Reject anything that isn't a PDF, or is too big.

    We sniff the first few bytes of the stream rather than trusting
    `content_type` (which is whatever the browser claims it is — trivially
    spoofable). Django's `UploadedFile.read(n)` + `.seek(0)` is safe for
    in-memory and temp-file uploads alike.
    """
    if file_obj is None:
        return None
    # Size first — cheap check, rejects oversized uploads before we touch
    # the stream. Django's framework-level DATA_UPLOAD_MAX_MEMORY_SIZE is a
    # second line of defense for ill-behaved clients.
    size = getattr(file_obj, "size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError(
            f"{field_label} is too large ({size} bytes). Maximum is {MAX_UPLOAD_BYTES} bytes (10 MB)."
        )
    # Magic-byte sniff.
    head = file_obj.read(len(PDF_MAGIC))
    try:
        file_obj.seek(0)
    except Exception:
        # Some storage backends may not support seek — in that case we
        # accept the read cost of one more pass. Nothing to do here.
        pass
    if not head.startswith(PDF_MAGIC):
        raise serializers.ValidationError(
            f"{field_label} must be a PDF document (magic bytes did not match)."
        )
    # Structural parse — rejects polyglot files (ZIP/HTML with a %PDF- prefix)
    # that sneak past the magic-byte check.
    try:
        PdfReader(file_obj, strict=False)
    except (PdfReadError, Exception) as exc:  # noqa: BLE001 — pypdf raises many types
        raise serializers.ValidationError(
            f"{field_label} is not a valid PDF: {exc}"
        ) from exc
    try:
        file_obj.seek(0)
    except Exception:
        pass
    return file_obj


class ContractSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id", "project", "title", "file", "file_url", "content", "text_source",
            "status", "created_by", "created_at", "updated_at", "activated_at",
        ]
        read_only_fields = ["id", "file_url", "created_by", "created_at", "updated_at", "activated_at"]

    def get_file_url(self, obj: Contract) -> str | None:
        # Route downloads through the authenticated ContractDownloadView
        # (finding #4) — the raw /media/ URL is no longer exposed in prod.
        if not obj.file:
            return None
        request = self.context.get("request")
        path = f"/api/contracts/{obj.pk}/download/"
        if request:
            return request.build_absolute_uri(path)
        return path

    def validate_file(self, value):
        return _validate_pdf_upload(value, "Contract file")

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ContractRequestSerializer(serializers.ModelSerializer):
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = ContractRequest
        fields = [
            "id", "account", "project", "description",
            "attachment", "attachment_url",
            "status", "review_comment",
            "created_at", "reviewed_at", "reviewed_by",
        ]
        # `account` is resolved server-side from the project — the client only
        # supplies `project`, `description`, and (optionally) `attachment`.
        # `review_comment` is set via the approve/reject endpoints, not on
        # create, so it's read-only here.
        read_only_fields = [
            "id", "account", "attachment_url", "status", "review_comment",
            "created_at", "reviewed_at", "reviewed_by",
        ]

    def get_attachment_url(self, obj: ContractRequest) -> str | None:
        # Route downloads through the authenticated
        # ContractRequestAttachmentView (finding #4).
        if not obj.attachment:
            return None
        request = self.context.get("request")
        path = f"/api/contract-requests/{obj.pk}/attachment/"
        if request:
            return request.build_absolute_uri(path)
        return path

    def validate_attachment(self, value):
        return _validate_pdf_upload(value, "Attachment")

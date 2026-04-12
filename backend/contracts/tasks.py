"""Background tasks for the contracts app.

Text extraction pipeline:
1. **pypdf** — fast, zero-cost, works for digital PDFs (most contracts).
2. **AWS Textract** — OCR fallback for scanned/image-only PDFs. Called only
   when pypdf returns empty text on a multi-page PDF. Requires AWS credentials
   and `AWS_REGION` to be set; degrades gracefully if unavailable.

Extracted text is stored in `Contract.content` and is the source of truth
for the AI classification pipeline's specialized topic agents.
"""

from __future__ import annotations

import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)


def _extract_with_pypdf(file_path: str) -> str:
    """Try extracting text with pypdf (digital PDFs)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("_extract_with_pypdf: pypdf is not installed")
        return ""

    try:
        reader = PdfReader(file_path)
    except Exception:
        logger.exception("_extract_with_pypdf: failed to open PDF")
        return ""

    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            logger.exception("_extract_with_pypdf: page extraction failed")
            pages_text.append("")

    return "\n\n".join(p.strip() for p in pages_text if p.strip())


def _extract_with_textract(file_path: str) -> str:
    """OCR fallback using AWS Textract's synchronous DetectDocumentText API.

    For PDFs, Textract requires the document to be in S3 or passed as bytes.
    We use the bytes approach (max 5 MB for sync, 500 MB for async). For
    documents over 5 MB, the async StartDocumentTextDetection API is needed.

    Returns extracted text or empty string on failure.
    """
    from django.conf import settings

    region = getattr(settings, "AWS_REGION", "") or ""
    if not region:
        logger.info("_extract_with_textract: AWS_REGION not set — skipping Textract")
        return ""

    try:
        import boto3
    except ImportError:
        logger.warning("_extract_with_textract: boto3 not installed")
        return ""

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except Exception:
        logger.exception("_extract_with_textract: failed to read file")
        return ""

    file_size_mb = len(file_bytes) / (1024 * 1024)

    # Build boto3 client kwargs — use explicit credentials if provided,
    # otherwise fall back to IAM role / instance profile / env vars.
    client_kwargs: dict = {"region_name": region}
    aws_key = getattr(settings, "AWS_ACCESS_KEY_ID", "") or ""
    aws_secret = getattr(settings, "AWS_SECRET_ACCESS_KEY", "") or ""
    if aws_key and aws_secret:
        client_kwargs["aws_access_key_id"] = aws_key
        client_kwargs["aws_secret_access_key"] = aws_secret

    try:
        textract = boto3.client("textract", **client_kwargs)
    except Exception:
        logger.exception("_extract_with_textract: failed to create Textract client")
        return ""

    if file_size_mb <= 5:
        # Synchronous API — works for images and single-page PDFs under 5 MB
        return _textract_sync(textract, file_bytes)
    else:
        # For larger PDFs, use the async API with S3
        # For now, fall back gracefully — the async path requires S3 upload
        logger.warning(
            "_extract_with_textract: file is %.1f MB (>5 MB sync limit). "
            "Async Textract requires S3 — skipping OCR for now.",
            file_size_mb,
        )
        return ""


def _textract_sync(client, file_bytes: bytes) -> str:
    """Call Textract DetectDocumentText synchronously."""
    try:
        response = client.detect_document_text(
            Document={"Bytes": file_bytes}
        )
    except Exception:
        logger.exception("_textract_sync: Textract API call failed")
        return ""

    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") == "LINE":
            text = block.get("Text", "")
            if text:
                lines.append(text)

    return "\n".join(lines)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def extract_contract_text(self, contract_id: str) -> None:
    """Extract text from a Contract's PDF file.

    Pipeline: pypdf first (fast, free) → Textract fallback (OCR for scans).
    Stores the result in `Contract.content` and records the extraction method
    in `Contract.text_source`.
    """
    from contracts.models import Contract

    try:
        contract = Contract.objects.get(pk=contract_id)
    except Contract.DoesNotExist:
        logger.error("extract_contract_text: contract %s not found", contract_id)
        return

    if not contract.file:
        logger.info("extract_contract_text: contract %s has no file, skipping", contract_id)
        return

    file_path = contract.file.path

    # Stage 1: pypdf (digital PDF)
    full_text = _extract_with_pypdf(file_path)
    text_source = Contract.TEXT_SOURCE_PYPDF

    if not full_text:
        # Stage 2: AWS Textract (OCR for scanned PDFs)
        logger.info(
            "extract_contract_text: pypdf returned empty for contract %s — "
            "trying AWS Textract OCR fallback",
            contract_id,
        )
        full_text = _extract_with_textract(file_path)
        text_source = Contract.TEXT_SOURCE_TEXTRACT if full_text else Contract.TEXT_SOURCE_NONE

    if not full_text:
        logger.warning(
            "extract_contract_text: both pypdf and Textract returned empty for "
            "contract %s — user can paste text manually",
            contract_id,
        )
        contract.text_source = Contract.TEXT_SOURCE_NONE
        contract.save(update_fields=["text_source"])
        return

    contract.content = full_text
    contract.text_source = text_source
    contract.save(update_fields=["content", "text_source"])
    logger.info(
        "extract_contract_text: extracted %d chars via %s for contract %s",
        len(full_text),
        text_source,
        contract_id,
    )

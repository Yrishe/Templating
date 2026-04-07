"""Background tasks for the contracts app.

Currently provides PDF text extraction (Phase 3 item 9). Extracted text is
stored in `Contract.content` and is the source of truth for Claude's
contract-grounded reply suggestions in `email_organiser.tasks`.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def extract_contract_text(self, contract_id: str) -> None:
    """Extract text from a Contract's PDF file and store it on `Contract.content`.

    Uses `pypdf` for digital PDFs (most contracts). For scanned/image PDFs the
    extraction will return empty text — a follow-up enhancement can add an OCR
    fallback (e.g. `ocrmypdf`/Tesseract).
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

    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(
            "extract_contract_text: pypdf is not installed — install it with "
            "`pip install pypdf` to enable contract text extraction."
        )
        return

    try:
        reader = PdfReader(contract.file.path)
    except Exception:
        logger.exception(
            "extract_contract_text: failed to open PDF for contract %s", contract_id
        )
        return

    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            logger.exception("extract_contract_text: page extraction failed")
            pages_text.append("")

    full_text = "\n\n".join(p.strip() for p in pages_text if p.strip())

    if not full_text:
        # Likely a scanned/image-only PDF. Leave content empty so the user can
        # paste plain text manually as a fallback.
        logger.warning(
            "extract_contract_text: contract %s produced empty text "
            "(probably scanned/image-only PDF)",
            contract_id,
        )
        return

    contract.content = full_text
    contract.save(update_fields=["content"])
    logger.info(
        "extract_contract_text: extracted %d chars for contract %s",
        len(full_text),
        contract_id,
    )

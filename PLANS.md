# Development Plans

Plan to finish the application by completing the deferred items from the
Phase 3 changelog. Tackle in order — each section is a self-contained work
unit.

---

## 1. SES Inbound + SNS verification

The current webhook (`backend/email_organiser/views.py::InboundEmailWebhookView`)
accepts a generic JSON shape authenticated by a shared `X-Webhook-Secret`
header. That's fine for `curl` testing but unsafe to expose publicly because:

- SES doesn't POST that shape — it publishes to SNS, which sends a very
  different envelope.
- Anyone who learns the secret can forge inbound mail. SNS uses signed
  messages (X.509 cert + signature) so we can cryptographically verify each
  delivery actually came from AWS.
- SNS also sends subscription confirmation requests that must be handled or
  the topic never starts delivering.

### Step 0 — Decisions to make first

1. **AWS or GCP?** SES Inbound only exists in AWS. If deploying to GCP Cloud
   Run, use SendGrid Inbound Parse or Mailgun Routes instead — adapter shape
   differs. CLAUDE.md lists both; pick one before starting.
2. **Verified SES domain?** (e.g. `inbound.contractmgr.app`) Inbound requires
   domain verification + MX records, which can take a day to propagate. If
   not in place, kick off in parallel.
3. **SES region** — Inbound is only available in a handful of regions
   (`us-east-1`, `us-west-2`, `eu-west-1`, etc.). Pick one.
4. **Delivery mode** — SES Inbound can deliver to SNS directly (small
   messages, ≤150KB, base64 raw email in the SNS payload) **or** write to S3
   and send an S3 pointer via SNS (any size). **Recommendation: S3 + SNS
   pointer**, because real emails with attachments blow past 150KB easily.

### Step 1 — AWS-side setup (console / Terraform; no code yet)

1. Verify the inbound domain in SES → add the TXT/DKIM records to DNS.
2. Add the **MX record** pointing to `inbound-smtp.<region>.amazonaws.com`
   (priority 10).
3. Create an **S3 bucket** for raw inbound mail (e.g.
   `contractmgr-inbound-mail`). Apply the SES bucket policy (AWS provides
   the snippet).
4. Create an **SNS topic** (e.g. `contractmgr-inbound-mail-topic`).
5. Create a **Receipt Rule Set** in SES with a single rule that: matches
   recipients `*@inbound.contractmgr.app`, action 1 = "Deliver to S3
   bucket", action 2 = "Publish to SNS topic". Activate the rule set.
6. Create an **SNS subscription**: protocol HTTPS, endpoint =
   `https://api.contractmgr.app/api/webhooks/inbound-email/ses/`. AWS will
   immediately POST a `SubscriptionConfirmation` to that URL — our endpoint
   must handle it (Step 3).
7. Create an **IAM user / role** the Django app can use to read from the S3
   bucket (`s3:GetObject` on that bucket only).

### Step 2 — Backend dependencies

Add to `backend/requirements/base.txt`:

```
boto3==1.34.0
sns-message-validator==0.0.5
```

Alternative for SNS verification: hand-rolled using `cryptography` (already
a transitive dep of most Django stacks). More code, no extra dep. Start
with the package; swap if security review pushes back.

New env vars in `config/settings/base.py` and `.env.example`:

```
AWS_REGION=us-east-1
AWS_INBOUND_S3_BUCKET=contractmgr-inbound-mail
AWS_ACCESS_KEY_ID=...           # or use IAM role on ECS
AWS_SECRET_ACCESS_KEY=...
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:contractmgr-inbound-mail-topic
```

### Step 3 — New view: `SESInboundWebhookView`

A **separate** endpoint at `/api/webhooks/inbound-email/ses/` that:

1. Reads `x-amz-sns-message-type` header to branch on message type.
2. **`SubscriptionConfirmation`**: validate signature → fetch the
   `SubscribeURL` once (this is how AWS "handshakes" with the endpoint) →
   return 200. **Critical:** without this the topic never starts
   delivering.
3. **`Notification`**: validate signature using `sns-message-validator`
   (checks the X.509 cert chain back to AWS, validates `SigningCertURL` is
   on `*.amazonaws.com`, recomputes the signature over the canonical
   message body, and rejects forgeries) → assert
   `TopicArn == settings.SNS_TOPIC_ARN` (defense in depth) → parse
   `Message` JSON.
4. Extract S3 pointer from the SES notification: `bucketName` +
   `objectKey` under `receipt.action`.
5. Fetch the raw RFC822 email from S3 with
   `boto3.client('s3').get_object(...)`.
6. Parse the raw email with stdlib `email.message_from_bytes` → extract
   `From`, `To`, `Subject`, `Message-ID`, `Date`, plain-text body, HTML
   body.
7. Reuse existing logic from `InboundEmailWebhookView`: look up project by
   `to`, dedupe by `message_id`, create `IncomingEmail`, enqueue
   `generate_suggested_reply.delay(...)`.
8. **`UnsubscribeConfirmation`**: log and 200, no action needed.

The cleanest refactor is to extract the project-lookup +
IncomingEmail-creation logic out of the existing generic view into a
private helper (e.g. `_ingest_inbound_email(project_email, sender,
subject, body_plain, body_html, message_id, raw_payload)`), then have
**both** the generic view and the new SES view call it.

### Step 4 — URL registration

`backend/email_organiser/urls.py`:

```python
path('webhooks/inbound-email/ses/', SESInboundWebhookView.as_view(), name='ses-inbound-webhook'),
```

Keep the old `/api/webhooks/inbound-email/` route as the dev/test path
(gated by `DEBUG` or behind a feature flag in production).

### Step 5 — Tests

Three unit tests minimum, all using `unittest.mock` so no real AWS calls:

1. **Subscription confirmation** is honored: POST a
   `SubscriptionConfirmation` shape, mock `urllib.request.urlopen` for the
   SubscribeURL fetch, assert it's called and 200 is returned.
2. **Valid notification** gets ingested: POST a `Notification` shape,
   monkeypatch `sns-message-validator` to return valid, mock `boto3`
   `s3.get_object` to return a canned RFC822 blob, assert an
   `IncomingEmail` row is created and `generate_suggested_reply.delay` is
   called.
3. **Forged signature is rejected**: POST a `Notification` with a tampered
   signature, assert 403 and **no** `IncomingEmail` is created.

### Step 6 — Production hardening checklist (before flipping DNS)

- [ ] Endpoint is HTTPS only (SNS will not POST to plain HTTP).
- [ ] WAF rule allowing only SNS source IPs (optional but cheap — AWS
      publishes them in `ip-ranges.json`).
- [ ] Generic webhook (`/api/webhooks/inbound-email/`) is disabled in
      production settings, OR its secret is rotated and stored only in
      Secrets Manager.
- [ ] CloudWatch alarm on 4xx/5xx rate from the SES rule's SNS topic.
- [ ] DLQ on the SNS topic so failed deliveries don't vanish.
- [ ] Bucket lifecycle rule to purge raw inbound emails after 30 days
      (PII).
- [ ] Run an end-to-end test by sending a real email to
      `proj-<uuid8>@inbound.contractmgr.app` and watching the
      `FinalResponse` appear.

---

## 2. OCR fallback for scanned PDFs

Currently `backend/contracts/tasks.py::extract_contract_text` uses `pypdf`,
which only handles digital PDFs. Scanned/image-only contracts return an
empty string and the task logs a warning. Need an OCR fallback so AI
suggestion replies still have contract context.

### Step 0 — Decisions

1. **System deps acceptable?** OCR requires Tesseract + Ghostscript +
   poppler-utils installed in the container. The Docker image grows by
   ~150 MB. Confirm this is OK before adding.
2. **Sync or async OCR?** OCR on a 50-page scan can take 30–60 s. The
   existing `extract_contract_text` Celery task is already async, so this
   is fine — but should run on a **separate queue** (`ocr` queue) so it
   doesn't block fast text extraction. Worth a dedicated worker pool in
   production.
3. **Languages?** `tesseract-ocr-eng` covers English. Add other language
   packs if multi-language contracts are expected.

### Step 1 — System dependencies

Update `backend/Dockerfile` (or whichever base image is used):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    ghostscript \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

For local dev on macOS: `brew install tesseract ghostscript poppler`.

### Step 2 — Python dependencies

Add to `backend/requirements/base.txt`:

```
ocrmypdf==16.4.0
```

`ocrmypdf` wraps Tesseract, handles deskewing/rotation, and produces a
searchable PDF + plain text output. Better than calling Tesseract
directly.

### Step 3 — Update `extract_contract_text`

In `backend/contracts/tasks.py`:

1. Run `pypdf` first as today.
2. If the joined text is empty (or under a threshold like 100 chars on a
   PDF with >1 page), assume scanned and fall back to OCR:
   - Create a temp file for output.
   - Call `ocrmypdf.ocr(input_path, output_path, sidecar=text_path,
     skip_text=True, force_ocr=False, language='eng')`.
   - Read the sidecar text file into `Contract.content`.
   - Clean up temp files in a `finally` block.
3. Wrap in `try/except ocrmypdf.exceptions.*` and degrade gracefully —
   log a warning and leave `content` empty if OCR also fails.
4. Add a `ContractTextSource` enum field on `Contract` (`pypdf` /
   `ocr` / `manual` / `none`) so the UI can show "extracted via OCR" and
   the user can paste plain text manually if quality is poor.

### Step 4 — Route OCR to its own Celery queue

In `backend/config/celery.py`:

```python
task_routes = {
    'contracts.tasks.extract_contract_text': {'queue': 'ocr'},
}
```

Update `docker-compose.yml` to add a second worker:

```yaml
celery-ocr:
  command: celery -A config worker -Q ocr -c 2
```

Keeps the default queue snappy for fast tasks.

### Step 5 — Frontend surface

- `frontend/src/components/contracts/contract-view.tsx`: when
  `text_source === 'ocr'`, show a small info banner: "Text extracted via
  OCR — quality may vary. Paste plain text manually if needed."
- Add a "Paste plain text" textarea fallback that PATCHes
  `Contract.content` directly.

### Step 6 — Tests

1. Unit test: `pypdf` succeeds → OCR is **not** called. Mock
   `ocrmypdf.ocr` and assert `call_count == 0`.
2. Unit test: `pypdf` returns empty → OCR is called and its sidecar text
   is persisted. Mock `ocrmypdf.ocr` to write a known text file.
3. Unit test: both `pypdf` and `ocrmypdf` fail → `Contract.content` stays
   empty, `text_source = 'none'`, no exception escapes the task.

### Step 7 — Production checklist

- [ ] Confirm Docker image size impact is acceptable (~150 MB).
- [ ] Provision the `ocr` worker pool with enough CPU (Tesseract is
      CPU-bound).
- [ ] Set a per-task timeout (e.g. 5 min) so a pathological PDF can't
      hang a worker forever.
- [ ] CloudWatch metric on OCR fallback rate — if it spikes, the user
      base is uploading mostly scans and we may want to invest in a
      better OCR service (AWS Textract, Google Document AI).

---

## 3. Backend tests for Phase 3 tasks/views

The Phase 3 changelog explicitly deferred backend tests for the inbound
webhook, PDF extraction, and Claude suggestion task because all three
involve external services (SES/SNS, pypdf, Anthropic) that need careful
mocking. This section is the dedicated session to add them.

### Step 0 — Test infrastructure

1. Confirm `pytest`, `pytest-django`, `pytest-mock`, and `factory-boy`
   are in `backend/requirements/dev.txt`. Add if missing.
2. Add `pytest-celery` for `CELERY_TASK_ALWAYS_EAGER=True` mode so tasks
   run inline in tests.
3. Create `backend/conftest.py` with shared fixtures:
   - `manager_user`, `account_user`, `invited_account_user`
   - `project_factory` with auto-generated `generic_email` and a default
     contract
   - `incoming_email_factory`
   - `mock_anthropic_client` — context manager that patches
     `anthropic.Anthropic` to return a canned response

### Step 1 — Tests for `InboundEmailWebhookView` (generic)

`backend/email_organiser/tests/test_inbound_webhook.py`:

1. **Missing secret header** → 401, no `IncomingEmail` created.
2. **Wrong secret** → 401.
3. **Valid secret + unknown `to` address** → 404, no row created.
4. **Valid secret + known project** → 201, `IncomingEmail` row created,
   `generate_suggested_reply.delay` called once with the new ID.
5. **Duplicate `message_id`** → 200 (idempotent), only one row exists,
   task **not** re-enqueued.
6. **Missing `message_id`** in payload → falls back to a deterministic
   hash (or whatever the current behavior is — verify and lock it in).
7. **Suggestion task enqueue raises** (mock `delay` to raise) → still
   returns 201 and the `IncomingEmail` row exists. Verifies the "graceful
   degradation" claim from the changelog.

### Step 2 — Tests for `extract_contract_text`

`backend/contracts/tests/test_extract_contract_text.py`:

1. **Happy path**: contract with a small valid PDF → `Contract.content`
   is populated with the expected text. Use a tiny fixture PDF in
   `backend/contracts/tests/fixtures/sample.pdf` (one page, "Hello
   world").
2. **Missing file**: `Contract.file` is `None` → task exits cleanly,
   logs a warning, no exception, `content` unchanged.
3. **`pypdf` import missing**: monkeypatch `sys.modules['pypdf']` to
   `None` → task logs and exits without raising.
4. **Empty text** (image-only PDF, simulated by mocking
   `PdfReader.pages` to return pages with empty `extract_text`) → logs
   the "probably scanned" warning, leaves `content` empty.
5. **Re-running on the same contract** → idempotent (overwrites with
   same content, no error).

### Step 3 — Tests for `generate_suggested_reply`

`backend/email_organiser/tests/test_generate_suggested_reply.py`:

The hardest one — Anthropic SDK must be fully mocked.

1. **Happy path**: project has a contract with text, `IncomingEmail`
   exists, `ANTHROPIC_API_KEY` is set, mock `anthropic.Anthropic` to
   return a canned `Message` with `content[0].text = "Suggested reply
   body"` → assert a `FinalResponse` is created with
   `status='suggested'`, `is_ai_generated=True`,
   `source_incoming_email=<id>`, subject starts with `"Re: "`, content
   matches the canned text, and `IncomingEmail.is_processed = True`.
2. **No API key**: `ANTHROPIC_API_KEY=''` → placeholder draft created
   with the `[AI suggestion unavailable...]` text, `is_processed=True`,
   no Anthropic call attempted.
3. **`anthropic` SDK not installed**: monkeypatch
   `sys.modules['anthropic'] = None` → same placeholder behavior.
4. **API error then success on retry**: mock the client to raise
   `anthropic.APIError` once then return a valid response → assert the
   task retried and succeeded.
5. **API error exhausts retries**: mock to raise on every call → falls
   back to placeholder, `is_processed=True`.
6. **Project with no contract**: contract OneToOne is missing → task
   should still run; system prompt notes "no contract context
   available". Assert no exception.
7. **Contract text >50k chars**: assert it's truncated to 50000 in the
   prompt (verify by inspecting the call args to the mocked client).
8. **Incoming email body >20k chars**: assert it's truncated to 20000.
9. **Idempotency**: running the task twice on the same `IncomingEmail`
   should not create two `FinalResponse` rows. (May require a guard in
   the task — if so, add it as part of this work.)

### Step 4 — Tests for Phase 2 endpoints that shipped without coverage

While we're here, retrofit tests for the manager-approval workflow and
tag endpoints, which also shipped untested:

1. `PendingManagerApproveView` — only managers can call it; flips
   `is_active`; non-manager → 403.
2. `PendingManagerRejectView` — deletes the row; non-manager → 403.
3. `TagListCreateView` — any authenticated user can create; tag name
   uniqueness enforced.
4. `TagDetailView` — only managers can delete.

### Step 5 — CI gate

Once the suite passes locally:

1. Add `pytest --cov=. --cov-fail-under=70` to the CI step (the CLAUDE.md
   target is 80, but we're starting from near-zero coverage — ratchet up
   over time).
2. Document in `RUNNING.md` how to run the backend test suite.
3. Add a pre-commit hook that runs `pytest -x --ff` on changed files
   only, so failing tests block commits.

---

## Sequencing recommendation

1. **SES + SNS verification** first — without it the inbound flow can't
   safely go to production, which blocks the whole AI feature from being
   useful.
2. **Backend tests** second — once the SES adapter exists, the test
   session can cover both the generic and SES webhook variants in one
   pass, sharing fixtures.
3. **OCR fallback** last — it's an enhancement, not a blocker. Most
   contracts are digital PDFs and will work fine without OCR. Pick this
   up after the first round of real-user feedback indicates how often
   scans actually appear.

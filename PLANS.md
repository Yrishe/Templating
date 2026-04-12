# Development Plans

Plan to finish the application by completing the deferred items from the
Phase 3 changelog. Tackle in order — each section is a self-contained work
unit.

## Status tracker

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Inbound email ingestion | **Path B chosen — infra only** | API Gateway + SendGrid/Postmark; zero Django code; text body sufficient |
| 2 | OCR fallback for scanned PDFs | **Done** | pypdf → AWS Textract fallback + manual paste textarea |
| 3 | Backend tests for pipeline/views | **Done** | 26 tests in `test_email_pipeline.py` |
| 4 | Contract attachment validation | **Done** | `_validate_pdf_upload` + frontend `accept=".pdf"` + 10 MB cap |
| 5 | CSP hardening | **Done** | `frontend/src/middleware.ts` — enforced in prod, report-only in dev |
| 6 | Celery beat schedule | **Done** | `config/celery.py` — deadlines at 08:00 UTC, unresolved at 09:00 UTC |

---

## Plan 1 — Inbound email ingestion (the last pending item)

This is the **only remaining work** before the application is complete.

### The decision: two paths

#### Path A — Build `SESInboundWebhookView` (full SES + SNS + S3)

Emails flow: **Sender → SES Inbound → S3 (raw email) → SNS → Django view**

The Django view receives the raw RFC 822 email from S3 (headers, body,
attachments — everything), parses it with Python's stdlib `email` module,
and feeds it into the classification pipeline.

**Code work (~150 lines):**
- New view `SESInboundWebhookView` at `/api/webhooks/inbound-email/ses/`
- SNS signature validation (`sns-message-validator` package)
- S3 fetch of raw email (`boto3`, already in requirements)
- RFC 822 parsing with stdlib `email.message_from_bytes`
- Hands off to existing `classify_incoming_email.delay()`

**AWS infra setup (no code — console or Terraform):**

| Step | What | Where |
|------|------|-------|
| Verify inbound domain | TXT/DKIM records for `inbound.contractmgr.app` | DNS provider |
| MX record | Point to `inbound-smtp.<region>.amazonaws.com` | DNS provider |
| S3 bucket | `contractmgr-inbound-mail` with SES bucket policy | AWS |
| SNS topic | `contractmgr-inbound-mail-topic` | AWS |
| SES Receipt Rule | Match `*@inbound.contractmgr.app` → S3 + SNS | AWS |
| SNS subscription | HTTPS → the `/ses/` endpoint | AWS |
| IAM role | `s3:GetObject` on the inbound bucket | AWS |

**Production hardening checklist:**
- [ ] HTTPS-only endpoint (SNS won't POST to HTTP)
- [ ] WAF rule allowing SNS source IPs (optional)
- [ ] Disable generic webhook in prod or rotate its secret to Secrets Manager
- [ ] CloudWatch alarm on 4xx/5xx from the SNS topic
- [ ] DLQ on the SNS topic
- [ ] S3 lifecycle rule to purge raw emails after 30 days (PII)
- [ ] End-to-end test: send real email → verify `EmailAnalysis` + `TimelineEvent`

#### Path B — API Gateway + provider parse (defer SES view)

Emails flow: **Sender → SendGrid/Postmark → API Gateway (auth) → existing generic webhook**

SendGrid or Postmark receives the email, pre-parses it into a clean JSON
payload (sender, subject, body), and POSTs it to API Gateway. Gateway
handles authentication and forwards to the existing
`/api/webhooks/inbound-email/`. **Zero new Django code.**

**Infra setup:**
- SendGrid Inbound Parse or Postmark inbound (configure parse domain)
- API Gateway + one route with API key / Lambda authorizer
- Point the parse domain at the API Gateway URL

### Comparison

| | Path A (SES + SNS + S3) | Path B (API Gateway + provider) |
|---|---|---|
| **Email attachments** | Full access — raw email in S3, can extract PDFs, images, etc. | Text only — provider forwards subject/body fields; attachments need separate handling or are dropped |
| **New Django code** | ~150 lines | Zero |
| **AWS infra** | S3, SNS, SES receipt rules, MX records, IAM | API Gateway + one route + auth |
| **Provider dependency** | AWS only (SES receives email) | SendGrid or Postmark (receives) + API Gateway (auth) |
| **Cost** | Free tier covers most volume | SendGrid free up to 100/day; Postmark paid inbound |
| **Time to ship** | Longer — MX/DNS propagation, SES domain verification, SNS handshake | Shorter — no MX records if using provider subdomain |

### When to choose which

- **Path B (API Gateway)** if incoming emails are text-only — people
  writing about delays, costs, scope changes. The existing webhook handles
  this without any new code. Ships faster.

- **Path A (SES)** if inbound emails will carry **attachments that matter**
  — a supplier sending a PDF claim, a revised quote, damage photos. Only
  the raw MIME body from S3 gives access to those files.

> **Decision (2026-04-12):** Text body is enough — inbound emails won't
> carry attachments the system needs to process. **Go with Path B** (API
> Gateway + SendGrid/Postmark). Zero new Django code. Path A can be added
> later if attachment processing becomes a requirement.

### OCR alternatives (completed — for reference)

| Option | Pros | Cons |
|--------|------|------|
| ~~ocrmypdf + Tesseract~~ | Open-source, no API cost | +150 MB Docker, CPU-heavy |
| **AWS Textract** (implemented) | High accuracy, handles tables/forms | Per-page API cost |
| ~~Google Document AI~~ | Best for structured docs | Pricing, GCP lock-in |
| Manual paste (implemented) | Zero deps | No automation |

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
   `classify_incoming_email.delay(...)` (the 3-stage AI classification
   pipeline: classify → topic analysis → timeline event generation) and
   `create_incoming_email_notification.delay(...)`.
8. **`UnsubscribeConfirmation`**: log and 200, no action needed.

The cleanest refactor is to extract the project-lookup +
IncomingEmail-creation logic out of the existing generic view into a
private helper (e.g. `_ingest_inbound_email(project_email, sender,
subject, body_plain, body_html, message_id, raw_payload)`), then have
**both** the generic view and the new SES view call it.

> **NOTE (2026-04-12):** The Email Organiser no longer generates reply
> drafts (`FinalResponse`). It now runs a 3-stage AI pipeline:
> 1. `classify_incoming_email` — relevance + category classification
> 2. `analyse_email_by_topic` — contract-grounded risk assessment via
>    specialized topic agents (costs, delay, scope, etc.)
> 3. `generate_timeline_event_from_email` — auto-creates a TimelineEvent
>
> The SES webhook adapter should call `classify_incoming_email.delay()`
> instead of `generate_suggested_reply.delay()`.

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
      `EmailAnalysis` + auto-generated `TimelineEvent` appear (the old
      `FinalResponse` flow has been replaced by the classification
      pipeline).

---

## 2. OCR fallback for scanned PDFs

Currently `backend/contracts/tasks.py::extract_contract_text` uses `pypdf`,
which only handles digital PDFs. Scanned/image-only contracts return an
empty string and the task logs a warning. Need an OCR fallback so the AI
classification pipeline (specialized topic agents in
`email_organiser/tasks.py`) still has contract context for risk
assessment, mitigation, and contract-reference extraction.

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
   `classify_incoming_email.delay` called once with the new ID (replaced
   `generate_suggested_reply`).
5. **Duplicate `message_id`** → 200 (idempotent), only one row exists,
   task **not** re-enqueued.
6. **Missing `message_id`** in payload → falls back to a deterministic
   hash (or whatever the current behavior is — verify and lock it in).
7. **Classification task enqueue raises** (mock `delay` to raise) → still
   returns 201 and the `IncomingEmail` row exists. Verifies the "graceful
   degradation" claim.

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

### Step 3 — Tests for the AI classification pipeline

`backend/email_organiser/tests/test_classification_pipeline.py`:

The pipeline has 3 stages — each needs isolated tests with the Anthropic
SDK fully mocked.

**Stage 1 — `classify_incoming_email`:**
1. **Happy path (relevant)**: mock Claude to return
   `{"is_relevant": true, "relevance": "high", "category": "costs", "keywords": ["budget", "overrun"]}`
   → `IncomingEmail` fields updated, `analyse_email_by_topic.delay` called.
2. **Irrelevant email**: mock returns `{"is_relevant": false, ...}` →
   `is_relevant=False`, `category="irrelevant"`, `is_processed=True`,
   **no** stage 2 enqueued.
3. **No API key**: → falls back to `general`/`medium` defaults, still
   chains to stage 2.
4. **Malformed JSON from Claude**: → falls back to defaults gracefully.
5. **Invalid category value**: Claude returns a category not in choices →
   normalized to `"general"`.

**Stage 2 — `analyse_email_by_topic`:**
6. **Happy path**: mock returns valid analysis JSON → `EmailAnalysis`
   created with risk_level, risk_summary, contract_references, etc.
   `generate_timeline_event_from_email.delay` called.
7. **High-relevance email**: → `create_email_occurrence_notification.delay`
   also called.
8. **Project with no contract**: → analysis runs with fallback text, no
   exception.
9. **Contract text >50k chars**: assert truncated to 50000 in the prompt.

**Stage 3 — `generate_timeline_event_from_email`:**
10. **Happy path**: mock returns valid timeline JSON → `TimelineEvent`
    created, linked to `EmailAnalysis.generated_timeline_event`,
    `is_processed=True`.
11. **Claude unavailable**: → fallback event created with generic title
    from email subject + category.
12. **No analysis exists**: → marks `is_processed=True`, no event created.

**Cross-stage integration (CELERY_TASK_ALWAYS_EAGER):**
13. **Full pipeline end-to-end**: send a webhook, verify that an
    `IncomingEmail`, `EmailAnalysis`, and `TimelineEvent` are all created
    with the correct links between them.

**Notification tasks:**
14. `create_email_occurrence_notification` — creates a
    `EMAIL_HIGH_RELEVANCE` notification for the project.
15. `check_unresolved_email_occurrences` — emails >48h old and unresolved
    get one `EMAIL_OCCURRENCE_UNRESOLVED` notification (deduped).

**Endpoint tests:**
16. `POST .../resolve/` — marks `is_resolved=True`.
17. `POST .../reanalyse/` — resets `is_processed`, deletes analysis, enqueues
    `classify_incoming_email`.
18. `GET .../incoming-emails/?category=costs&relevance=high` — filters work.

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

## 4. Contract request attachment — file type & size limits

The Submit Contract Request form (added 2026-04-11) accepts any file type
with no size cap on `ContractRequest.attachment`. That's fine for dev but
needs to be tightened before production:

### Step 1 — Backend validation

In `backend/contracts/serializers.py::ContractRequestSerializer`, add a
`validate_attachment` method:

- **Allowed types**: start with PDF only (`application/pdf`), matching
  `Contract.file`. Detect via the first ~4 KB of the file magic (stdlib
  `mimetypes` is unreliable because the browser can lie in
  `Content-Type`). `python-magic` is the usual pick, but it adds a libmagic
  system dep; alternatively sniff the `%PDF-` header manually for a PDF-only
  allow-list and skip the extra dep.
- **Max size**: 10 MB feels right for a redlined contract PDF. Reject with
  a 400 + clear message on overflow. Also set Django's
  `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` in
  `config/settings/base.py` so the framework rejects oversized bodies
  before they hit the view.

### Step 2 — Frontend pre-checks

In `frontend/src/components/contracts/contract-view.tsx::SubmitRequestForm`:

- `<input type="file" accept="application/pdf">` to narrow the picker.
- Size check on `onChange` that surfaces an inline error before the user
  hits Submit — avoids a wasted round-trip on a 50 MB file.
- Mirror the size constant in a shared `lib/constants.ts` so the frontend
  and backend stay in sync if the limit changes.

### Step 3 — Tests

Two unit tests on the serializer:

1. Rejects a non-PDF upload (e.g. a `.png` with magic bytes of a PNG) with
   a field-level validation error.
2. Rejects a file larger than the configured max — mock the file size
   check so the test doesn't actually allocate 10 MB.

### Step 4 — Retroactive cleanup

If this ships after accounts have already uploaded non-PDF attachments
in dev, the stored files themselves don't need purging (they're opaque
blobs), but a one-off management command to list any `ContractRequest`
rows whose `attachment` content type is unknown could be useful for a
compliance sweep.

---

## 5. Harden CSP to mitigate the sessionStorage XSS surface

On 2026-04-12 the auth storage model changed from httpOnly cookies to
per-tab `sessionStorage` so multiple users can work side-by-side in
different tabs of the same browser. The trade-off is that JavaScript can
now read the access + refresh tokens, so an XSS vulnerability anywhere
in the frontend (or in a compromised dependency) would let an attacker
exfiltrate them.

The access token is short (15 minutes) and refreshes rotate with
blacklist-after-rotation, which limits the blast radius. The remaining
mitigation is a strict Content-Security-Policy to make XSS hard to
land in the first place. Pick this up before going to production.

### Step 1 — Pick a policy shape

- **Baseline**: `default-src 'self'; script-src 'self'; style-src 'self'
  'unsafe-inline'; img-src 'self' data:; connect-src 'self'
  <api-origin>; frame-ancestors 'none'; base-uri 'self'; form-action
  'self'`.
- `'unsafe-inline'` on `style-src` is a concession to Tailwind's runtime
  style injection. Can be removed later if we switch to a nonce-based
  style pipeline.
- `script-src` must NOT include `'unsafe-inline'` — that's the main
  thing standing between the app and a one-shot XSS → token exfiltration.
- `connect-src` has to list the backend origin (and the WebSocket
  endpoint for Channels) or fetch/WS calls get blocked.
- `frame-ancestors 'none'` = no one can iframe the app. Prevents
  clickjacking.

### Step 2 — Wire it up in Next.js

Next 16 supports middleware-level headers. Add
`frontend/src/middleware.ts`:

```ts
import { NextResponse, type NextRequest } from 'next/server'

export function middleware(_req: NextRequest) {
  const res = NextResponse.next()
  res.headers.set(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL} ${process.env.NEXT_PUBLIC_WS_URL}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; ')
  )
  // Extra defense in depth — these are cheap and the browser enforces them.
  res.headers.set('X-Content-Type-Options', 'nosniff')
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  res.headers.set('X-Frame-Options', 'DENY')
  return res
}

export const config = {
  matcher: '/((?!_next/static|_next/image|favicon.ico).*)',
}
```

### Step 3 — Report-only rollout

Next, deploy with `Content-Security-Policy-Report-Only` for one week
and hook the `report-uri` / `report-to` endpoint to a simple Django
view that logs violations. This catches any missed sources before the
policy actually blocks anything.

### Step 4 — Complementary hardening

- Move the refresh-token rotation cadence tighter (currently 7-day
  refresh lifetime): consider dropping refresh to 24 hours for sensitive
  accounts.
- Run `npm audit` + Snyk on CI — most XSS ships through a poisoned
  dependency, not app code.
- Audit every `dangerouslySetInnerHTML` usage (there should be none
  today) and any place we render Markdown from user input.

### Step 5 — Known limitations

- `sessionStorage` is still cleared when a tab closes; this is
  acceptable because it also limits token lifetime to the tab's
  lifespan. If we ever want "stay logged in across restart" UX, we'll
  have to either reintroduce httpOnly cookies (and drop the multi-tab
  feature) or accept `localStorage` + the corresponding XSS surface.

---

## 6. Schedule the deadline notification task

`backend/notifications/tasks.py::check_upcoming_deadlines` iterates
`TimelineEvent` rows approaching their `end_date` and emits a
`DEADLINE_UPCOMING` notification per event (dedup'd via
`triggered_by_timeline_event`). It's currently not scheduled — production
needs a Celery beat entry so it actually runs.

> **NOTE (2026-04-12):** `check_upcoming_deadlines` no longer uses a
> fixed `lookahead_days` argument. Each `TimelineEvent` now has its own
> `deadline_reminder_days` field (default 3) set by the project creator.
> The task iterates all non-completed events and checks whether
> `today >= end_date - deadline_reminder_days`. Also:
> `check_unresolved_email_occurrences` needs scheduling too — it flags
> email occurrences that have been unresolved for >48 hours.

### Step 1 — Register the beat schedule

Add to `backend/config/celery.py` (or a new `celerybeat.py` imported from
there):

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    "check-upcoming-deadlines-daily": {
        "task": "notifications.tasks.check_upcoming_deadlines",
        # 08:00 UTC each day — before most teams start, so the
        # notification is waiting when they log in.
        "schedule": crontab(hour=8, minute=0),
        # No kwargs needed — the task now reads each event's own
        # deadline_reminder_days field instead of a global lookahead.
    },
    "check-unresolved-email-occurrences-daily": {
        "task": "notifications.tasks.check_unresolved_email_occurrences",
        # 09:00 UTC — runs after the deadline check, flags emails
        # that have been unresolved for >48 hours.
        "schedule": crontab(hour=9, minute=0),
    },
}
```

`docker-compose.yml` already runs a `celery-beat` service, so this picks
up automatically on restart.

### Step 2 — Verify in staging

1. Backfill a handful of `TimelineEvent` rows with `end_date` approaching
   and various `deadline_reminder_days` values (1, 3, 7).
2. Trigger the task manually from a shell:
   `./manage.py shell -c "from notifications.tasks import check_upcoming_deadlines; print(check_upcoming_deadlines())"`
3. Confirm the return value equals the number of notifications created,
   and that a second run returns `0` (dedupe via the FK link).
4. For unresolved occurrences: create an `IncomingEmail` with
   `is_relevant=True`, `is_resolved=False`, `is_processed=True`,
   `received_at` >48h ago, then run `check_unresolved_email_occurrences()`
   and verify a notification is created.

### Step 3 — Tuning

- Each event's `deadline_reminder_days` is user-configurable on the
  timeline form (1–30 days). No global tuning needed.
- If unresolved email notifications are too noisy, consider increasing
  the 48-hour threshold or switching to one notification per project
  instead of per email.

---

## Completion status (as of 2026-04-12)

**5 of 6 items are done.** The only remaining work is Plan 1 (inbound
email ingestion), which requires a decision on Path A vs Path B — see the
detailed analysis at the top of this file.

| # | Item | Status |
|---|------|--------|
| 1 | Inbound email ingestion | Decision required → then infra setup + optional ~150-line view |
| 2 | OCR fallback | Done — pypdf → AWS Textract → manual paste |
| 3 | Backend tests | Done — 26 tests covering pipeline, webhook, endpoints, notifications |
| 4 | Contract attachment validation | Done — magic-byte PDF sniff + 10 MB cap (backend + frontend) |
| 5 | CSP hardening | Done — strict CSP in prod, report-only in dev, HSTS, Permissions-Policy |
| 6 | Celery beat schedule | Done — deadlines daily 08:00 UTC, unresolved occurrences 09:00 UTC |

### Next session — Path B infra setup (no Django code needed)

1. **Pick provider**: SendGrid Inbound Parse (free ≤100/day) or Postmark Inbound
2. **Configure parse domain**: point provider at a subdomain (e.g. `parse.contractmgr.app`)
3. **Create API Gateway**: one route → forward to `POST /api/webhooks/inbound-email/`
   with API key or Lambda authorizer for authentication
4. **Set `INBOUND_EMAIL_WEBHOOK_SECRET`** in production env (Secrets Manager)
5. **Disable generic webhook in prod** or ensure it's only reachable via API Gateway
6. **End-to-end test**: send a real email → verify `IncomingEmail` created →
   `EmailAnalysis` appears → `TimelineEvent` auto-generated on the project timeline

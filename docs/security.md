# Security Review

Snapshot date: 2026-04-19
Scope: full codebase at repo root (Django backend, Next.js frontend, Celery, docker-compose).

Findings are grouped by severity. Each item lists the file, line, a description of the risk, and a one-line remediation. Dependencies were not flagged as carrying critical CVEs at review time (Django 5.0.4, Next.js 16.2.2).

---

## Critical

### 1. Webhook secret comparison is not timing-safe
- **File:** [backend/email_organiser/views.py:208](../backend/email_organiser/views.py#L208)
- **Risk:** `provided_secret != expected_secret` uses plain string equality. An attacker can measure response-time differences to recover the secret byte-by-byte.
- **Fix:** Replace with `hmac.compare_digest(provided_secret, expected_secret)`.

---

## High

### 2. Insecure default DB password in settings
- **File:** [backend/config/settings/base.py:95](../backend/config/settings/base.py#L95)
- **Risk:** `DB_PASSWORD` falls back to the literal string `"postgres"` if the env var is missing. A misconfigured deploy would silently run with a trivial password.
- **Fix:** Remove the default; raise `ImproperlyConfigured` when `DB_PASSWORD`/`DB_USER` are missing.

### 3. `SECRET_KEY` has an insecure placeholder default
- **File:** [backend/config/settings/base.py:9](../backend/config/settings/base.py#L9)
- **Risk:** Missing `DJANGO_SECRET_KEY` falls back to `"django-insecure-placeholder-key-change-in-production"`. If inherited on a production boot, JWT/signing guarantees are gone.
- **Fix:** In `production.py`, explicitly require `DJANGO_SECRET_KEY` and fail startup if absent.

### 4. Uploaded files served directly from `MEDIA_ROOT` with no access control
- **Files:** [backend/config/urls.py:25](../backend/config/urls.py#L25), [backend/config/settings/base.py](../backend/config/settings/base.py) (`MEDIA_URL` / `MEDIA_ROOT`)
- **Risk:** Contract PDFs and attachments are served via Django's `static()` helper. Any authenticated (or even unauthenticated, depending on URL config) user who guesses a path can download another account's files — classic IDOR via filesystem.
- **Fix:** Serve uploads through an authenticated view that checks ownership/project membership, or issue short-lived signed URLs (e.g. S3 presigned).

### 5. JWTs stored in `sessionStorage`, no CSP enforced
- **Files:** [frontend/src/lib/api.ts:26-41](../frontend/src/lib/api.ts#L26-L41), [frontend/src/context/auth-context.tsx:51](../frontend/src/context/auth-context.tsx#L51)
- **Risk:** Access + refresh tokens live in `sessionStorage`, which is readable by any script on the origin. Combined with `Content-Security-Policy` being in `Report-Only` mode, any XSS immediately exfiltrates both tokens.
- **Fix:** Move to `HttpOnly` + `SameSite=Strict` cookies for refresh tokens, keep access tokens in memory only, and switch CSP from `Report-Only` to enforcing (remove `unsafe-inline` / `unsafe-eval` where possible).

---

## Medium

### 6. `ALLOWED_HOSTS` parsing produces `[""]` when env var missing
- **File:** [backend/config/settings/base.py:13](../backend/config/settings/base.py#L13)
- **Risk:** `os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")` returns `[""]`, not `[]`. The app then rejects every request (200→400 availability issue), and the error masks a misconfigured deploy.
- **Fix:** Split only if the env var is non-empty; raise `ImproperlyConfigured` in `production.py` when unset.

### 7. PDF validation is just a 5-byte magic-number check
- **File:** [backend/contracts/serializers.py:38-48](../backend/contracts/serializers.py#L38-L48)
- **Risk:** Only `%PDF-` is checked. Polyglot files (ZIP/HTML with a PDF prefix) pass validation and may be processed by `pypdf` or rendered by frontends expecting PDF.
- **Fix:** Validate structurally by parsing with `pypdf` / `pdfplumber` and rejecting on exception; enforce a size cap in the serializer.

### 8. `ContractActivateView` trusts `IsManager` without project-scoped check
- **File:** [backend/contracts/views.py:165](../backend/contracts/views.py#L165)
- **Risk:** Any user with the `IsManager` role can activate any contract by primary key — managers in unrelated projects can escalate state.
- **Fix:** Verify the requesting manager belongs to the contract's project before mutating state (mirror the `_require_project_membership` pattern used elsewhere).

### 9. Redis port exposed on `0.0.0.0`
- **File:** [docker-compose.yml:24](../docker-compose.yml#L24)
- **Risk:** Redis listens on all interfaces without auth. On a shared network (café, WeWork, cloud VM) anyone reachable can issue `FLUSHDB`/`CONFIG SET` or inject tasks.
- **Fix:** Bind to `127.0.0.1:6379` in dev; in prod drop the port mapping entirely and require `requirepass` + internal-network-only access.

### 10. Postgres port exposed on `0.0.0.0`
- **File:** [docker-compose.yml:10](../docker-compose.yml#L10)
- **Risk:** DB is reachable from the LAN. Credentials are the only barrier.
- **Fix:** Bind to `127.0.0.1:5434` (dev) or remove the mapping entirely in prod.

### 11. Inbound webhook has no rate limiting and stores full raw payload
- **Files:** [backend/email_organiser/views.py:211](../backend/email_organiser/views.py#L211), [backend/email_organiser/views.py:248](../backend/email_organiser/views.py#L248)
- **Risk:** Once the shared secret is known, an attacker can flood the endpoint and blow up DB storage via `raw_payload` (JSONField).
- **Fix:** Add DRF throttling to the view and cap `raw_payload` size (drop attachments beyond N KB, or store only a hash + minimal metadata).

---

## Low / informational

### 12. `INBOUND_EMAIL_WEBHOOK_SECRET` has a weak guidance placeholder
- **File:** [.env.example:42](../.env.example#L42)
- **Risk:** `"change-me-to-a-long-random-string"` is well-known documentation text. A copy-paste deploy uses a guessable secret.
- **Fix:** Leave the value blank in `.env.example`; document secret generation (`openssl rand -hex 32`).

### 13. Frontend size check is client-side only
- **File:** [frontend/src/components/contracts/contract-view.tsx:220](../frontend/src/components/contracts/contract-view.tsx#L220)
- **Risk:** Not exploitable (Django enforces size), but the client check can mislead reviewers into thinking it's a security control.
- **Fix:** Add a comment calling out that it's a UX hint only; the serializer is the source of truth.

---

## Areas checked and clean
- No `raw()` / `cursor.execute()` / `.extra()` SQL with user input.
- No `dangerouslySetInnerHTML` wired to untrusted content in the frontend.
- No hardcoded API keys or real credentials in the tree (fixtures use `password123` intentionally).
- No use of `subprocess`/`os.system` with user-controlled args.

## Tracking

Use this file as the starting point for a backlog. Each finding should become either a ticket (with this severity) or an explicit accepted-risk note once triaged.

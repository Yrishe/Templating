# Changelog

All notable changes to this project will be documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); dates are UTC.

## [Unreleased]

### Next up

- **Phase 1 of the research program** (~3 days) — AI-suggestion thumbs. See [docs/research.md](docs/research.md#a1-ai-suggestion-thumbs) and the `[research]` entry in [docs/plan.md](docs/plan.md). Delivers a labelled eval dataset for the email organiser.

### Security fixes (planned)

Tracking items from [docs/security.md](docs/security.md). Status: **planned** — none implemented yet. Move each bullet under **Security fixes** once landed and link the commit.

#### Critical
- [x] **#1 Webhook timing-safe comparison** — replaced `!=` with `hmac.compare_digest` in [backend/email_organiser/views.py](backend/email_organiser/views.py); unconfigured `INBOUND_EMAIL_WEBHOOK_SECRET` now returns `503` and logs an error instead of silently 401'ing.

#### High
- [x] **#2 Drop `DB_PASSWORD`/`DB_USER`/`DB_NAME`/`DB_HOST` defaults** — added `_require_env()` helper in [backend/config/settings/base.py](backend/config/settings/base.py); missing DB env vars now raise `ImproperlyConfigured` at import time.
- [x] **#3 `SECRET_KEY` fail-fast in production** — [backend/config/settings/production.py](backend/config/settings/production.py) now reads `DJANGO_SECRET_KEY` via `_require_env()`, so the dev placeholder can never be inherited in prod. Dev fallback in `base.py` is kept with a comment.
- [x] **#4 Access-controlled media serving** — `static(MEDIA_URL, ...)` is now gated behind `DEBUG` in [backend/config/urls.py](backend/config/urls.py). New `ContractDownloadView` and `ContractRequestAttachmentView` stream uploads after checking project membership (managers keep global oversight). Serializers now emit the authenticated API URL; frontend uses a new `downloadAuthed` helper in [frontend/src/lib/api.ts](frontend/src/lib/api.ts) that fetches the blob with `Authorization: Bearer` and triggers a client-side download.
- [x] **#5 JWT storage hardening** — refresh token moved to an `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api/auth/` ([backend/accounts/views.py](backend/accounts/views.py), [backend/config/settings/base.py](backend/config/settings/base.py)); access token held in memory only via `accessTokenStore` ([frontend/src/lib/api.ts](frontend/src/lib/api.ts)); `AuthContext` boots by calling `/api/auth/token/refresh/` which reads the cookie ([frontend/src/context/auth-context.tsx](frontend/src/context/auth-context.tsx)). CSP is already prod-enforced with `script-src 'self'` so the "flip from Report-Only" sub-task was dropped as stale. Multi-tab different-users support removed deliberately — cookies are per-origin and this was the agreed trade.

#### Medium
- [x] **#6 `ALLOWED_HOSTS` parsing** — filter empty entries from the split in [backend/config/settings/base.py](backend/config/settings/base.py); [backend/config/settings/production.py](backend/config/settings/production.py) now raises `ImproperlyConfigured` when the resulting list is empty.
- [x] **#7 Structural PDF validation** — [backend/contracts/serializers.py](backend/contracts/serializers.py) now parses uploads through `pypdf.PdfReader` after the magic-byte check, rejecting polyglots that fake a `%PDF-` prefix.
- [x] **#8 `ContractActivateView` membership check** — **accepted-risk**. Managers have global oversight across every contract view (`ContractListCreateView`, `ContractDetailView`, approve/reject), so scoping only activation would be inconsistent. Captured as a future design change in [docs/plan.md](docs/plan.md); tightens naturally when multi-company/multi-tenant support lands.
- [x] **#9 Redis bind to `127.0.0.1`** — [docker-compose.yml](docker-compose.yml) drops the host-port mapping entirely. Redis is only reachable over the docker network (`redis:6379`) — not even loopback — which is strictly more restrictive than the original finding asked for.
- [x] **#10 Postgres bind to `127.0.0.1`** — [docker-compose.yml](docker-compose.yml) port mapping scoped to loopback; LAN peers can no longer hit the Postgres listener.
- [x] **#11 Inbound webhook throttle + payload cap** — [backend/email_organiser/views.py](backend/email_organiser/views.py) now uses `ScopedRateThrottle` (scope `"inbound_email"`, 60/min; rate registered in [base.py](backend/config/settings/base.py)) and replaces `raw_payload` with `{size, sha256, _truncated}` metadata when the serialized JSON exceeds 256 KB.

#### Low
- [x] **#12 Clean `.env.example` webhook placeholder** — [.env.example](.env.example) value blanked, added `openssl rand -hex 32` generation hint so a copy-paste deploy can't end up with the old documentation string.
- [x] **#13 Frontend file-size check comment** — [frontend/src/components/contracts/contract-view.tsx](frontend/src/components/contracts/contract-view.tsx) annotated so future readers don't mistake the client-side size gate for a security control.

### Fixed
- **Invited-account users could not see any project** — every permission check across the app filters by `ProjectMembership`, but `/api/projects/<id>/invite/` only created an `InvitedAccount` row. Result: empty project list + 404 on every nested project tab (chat/contract/change-requests/timeline/invite). [backend/email_organiser/views.py](backend/email_organiser/views.py) `ProjectInviteView.post()` now also `get_or_create`s a `ProjectMembership` so the two invite paths are symmetric. Fixture [backend/fixtures/initial_data.json](backend/fixtures/initial_data.json) gains the matching `projectmembership` row for the seeded invited user. Regression test in [backend/tests/test_permissions.py](backend/tests/test_permissions.py). Closes Issue B from the 2026-04-20 browser smoke.

### Added
- **Per-feature feedback widget (Phase 1.5)** — `FeatureFeedback` model + `POST /api/feedback/feature/` endpoint + `<FeatureFeedback>` React component that takes `featureKey` (dotted, e.g. `dashboard.home`, `projects.overview`) and an optional `projectId`. Mounted on the dashboard, the project overview page, and the email-organiser analysis panel so users can rate each feature 👍/👎 with an optional comment. Gated by `FEATURE_FEATURE_FEEDBACK` flag, exposed through `/api/auth/me/features.feature_feedback`. Idempotent upsert keyed on `(user, feature_key, project)` — same pattern as Phase 1 AI thumbs. 14 regression tests in [backend/tests/test_feature_feedback.py](backend/tests/test_feature_feedback.py). Deliberately narrower than the Phase 2 `AppFeedback` sketch in [docs/research.md](docs/research.md) — no floating button, no route auto-capture, no n8n fan-out yet; that's deferred with the support-tool decision.
- [backend/email_organiser/management/commands/simulate_inbound_email.py](backend/email_organiser/management/commands/simulate_inbound_email.py) — dev-only `python manage.py simulate_inbound_email` that creates an `IncomingEmail` and fires the same Celery fan-out the webhook does (notification + AI classification). Resolves a project by UUID or `generic_email`. Closes Issue A from the 2026-04-20 browser smoke.
- [docs/research.md](docs/research.md) — adopted user-feedback program combining in-app capture (AI thumbs + floating widget) with a structured research layer (quarterly NPS, interview opt-in). Data models, endpoints, privacy/retention, and 5-phase implementation slice defined.
- [docs/support.md](docs/support.md) — customer-support surface and event-bus plan. Chatwoot (self-hosted) as system of record; n8n as the fan-out bus for feedback/support events. SLA table, webhook-security pattern, and 5-phase rollout defined.
- [docs/plan.md](docs/plan.md) index updated with `[research]` and `[support]` pointer entries so the two adopted programs are discoverable from the central plan file.
- [docs/security.md](docs/security.md) — full security review of the current codebase (13 findings across critical/high/medium/low).
- [docs/frontend.md](docs/frontend.md), [docs/backend.md](docs/backend.md), [docs/email_organiser.md](docs/email_organiser.md) — per-area feature documentation templates.
- [REQUIREMENTS.md](REQUIREMENTS.md) — project requirements (functional, non-functional, security, compliance).
- [CHANGELOG.md](CHANGELOG.md) — this file.
- `.env` created locally from [.env.example](.env.example) with a freshly generated `DJANGO_SECRET_KEY` (not committed).

### Changed
- [frontend/Dockerfile:9](frontend/Dockerfile#L9) — `npm ci --frozen-lockfile` → `npm ci --legacy-peer-deps`. The lockfile pins `eslint@8.x` but `eslint-config-next@16.2.2` requires `eslint@>=9`, so strict resolution failed on image build. `--legacy-peer-deps` unblocks install without changing the runtime tree.
- [docker-compose.yml:93](docker-compose.yml#L93) — frontend service `npm install` now also passes `--legacy-peer-deps` (same reason as above; otherwise the dev container `npm install` step fails on start).
- [docker-compose.yml:10](docker-compose.yml#L10) — Postgres host-port mapping `5432:5432` → `5434:5432`. The local machine already had Postgres bound to 5432 and 5433, preventing the container from starting. Inside the compose network the DB still listens on 5432, so `DB_HOST=postgres` / `DB_PORT=5432` in `.env` remain correct.

### Setup actions taken (not code changes)
- Cloned `https://github.com/Yrishe/Templating.git` into `Development/Management/`.
- `docker compose up --build -d` — all six services (postgres, redis, backend, celery, celery-beat, frontend) running.
- `docker compose exec backend python manage.py migrate` — all migrations applied cleanly.
- `docker compose exec backend python manage.py loaddata fixtures/users.json fixtures/initial_data.json` — 34 objects loaded.
- Set `alice.manager@example.com` password to `password123` via `manage.py shell` per [RUNNING.md](RUNNING.md).

### Verified
- Frontend reachable at http://localhost:3000 (HTTP 307 → `/login`, HTTP 200).
- Backend Swagger UI at http://localhost:8000/api/docs/ (HTTP 200).
- Django admin at http://localhost:8000/admin/ (HTTP 302 to login).

---

_Maintainers: append new entries at the top of `[Unreleased]`. When cutting a release, rename the section to the version number + date._

# Changelog

All notable changes to this project will be documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); dates are UTC.

## [Unreleased]

### Security fixes (planned)

Tracking items from [docs/security.md](docs/security.md). Status: **planned** — none implemented yet. Move each bullet under **Security fixes** once landed and link the commit.

#### Critical
- [x] **#1 Webhook timing-safe comparison** — replaced `!=` with `hmac.compare_digest` in [backend/email_organiser/views.py](backend/email_organiser/views.py); unconfigured `INBOUND_EMAIL_WEBHOOK_SECRET` now returns `503` and logs an error instead of silently 401'ing.

#### High
- [x] **#2 Drop `DB_PASSWORD`/`DB_USER`/`DB_NAME`/`DB_HOST` defaults** — added `_require_env()` helper in [backend/config/settings/base.py](backend/config/settings/base.py); missing DB env vars now raise `ImproperlyConfigured` at import time.
- [x] **#3 `SECRET_KEY` fail-fast in production** — [backend/config/settings/production.py](backend/config/settings/production.py) now reads `DJANGO_SECRET_KEY` via `_require_env()`, so the dev placeholder can never be inherited in prod. Dev fallback in `base.py` is kept with a comment.
- [x] **#4 Access-controlled media serving** — `static(MEDIA_URL, ...)` is now gated behind `DEBUG` in [backend/config/urls.py](backend/config/urls.py). New `ContractDownloadView` and `ContractRequestAttachmentView` stream uploads after checking project membership (managers keep global oversight). Serializers now emit the authenticated API URL; frontend uses a new `downloadAuthed` helper in [frontend/src/lib/api.ts](frontend/src/lib/api.ts) that fetches the blob with `Authorization: Bearer` and triggers a client-side download.
- [ ] **#5 JWT storage + CSP hardening** — refresh token in `HttpOnly; Secure; SameSite=Strict` cookie, access token in memory only ([frontend/src/lib/api.ts:26-41](frontend/src/lib/api.ts#L26-L41), [frontend/src/context/auth-context.tsx:51](frontend/src/context/auth-context.tsx#L51)); flip CSP from `Report-Only` to enforcing; drop `unsafe-inline` for scripts.

#### Medium
- [x] **#6 `ALLOWED_HOSTS` parsing** — filter empty entries from the split in [backend/config/settings/base.py](backend/config/settings/base.py); [backend/config/settings/production.py](backend/config/settings/production.py) now raises `ImproperlyConfigured` when the resulting list is empty.
- [x] **#7 Structural PDF validation** — [backend/contracts/serializers.py](backend/contracts/serializers.py) now parses uploads through `pypdf.PdfReader` after the magic-byte check, rejecting polyglots that fake a `%PDF-` prefix.
- [x] **#8 `ContractActivateView` membership check** — **accepted-risk**. Managers have global oversight across every contract view (`ContractListCreateView`, `ContractDetailView`, approve/reject), so scoping only activation would be inconsistent. Captured as a future design change in [docs/plan.md](docs/plan.md); tightens naturally when multi-company/multi-tenant support lands.
- [ ] **#9 Redis bind to `127.0.0.1`** — [docker-compose.yml:24](docker-compose.yml#L24); `"6379:6379"` → `"127.0.0.1:6379:6379"`.
- [ ] **#10 Postgres bind to `127.0.0.1`** — [docker-compose.yml:10](docker-compose.yml#L10); `"5434:5432"` → `"127.0.0.1:5434:5432"`.
- [ ] **#11 Inbound webhook throttle + payload cap** — [backend/email_organiser/views.py:211](backend/email_organiser/views.py#L211); add `ScopedRateThrottle` (scope `"inbound_email"`, 60/min); drop `raw_payload` fields > 256 KB or replace with hash + size.

#### Low
- [ ] **#12 Clean `.env.example` webhook placeholder** — [.env.example:42](.env.example#L42); blank the value, add `# openssl rand -hex 32` hint.
- [ ] **#13 Frontend file-size check comment** — [frontend/src/components/contracts/contract-view.tsx:220](frontend/src/components/contracts/contract-view.tsx#L220); annotate as UX hint only.

### Added
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

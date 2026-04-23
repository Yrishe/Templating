# Deployment plan — road to first production deploy

_Last updated: 2026-04-22. Host decided: **Render + Brevo + Cloudflare + Sentry**. Deploy artifacts landed; see [deploy_runbook.md](deploy_runbook.md) for the step-by-step._

## Current state (on `main`)

**Shipped and ready to deploy behind:**

- **Security review (13 findings)** — all closed (#8 accepted-risk, reopens when per-project manager scoping lands). See [docs/security.md](security.md) + the `security(#N)` commits.
- **Auth model (Security #5)** — refresh token in `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api/auth/`; access token in JS module-ref. Multi-tab different-users deliberately dropped. Decisions: [docs/security_5_plan.md](security_5_plan.md).
- **Test suite** — 132 backend tests green (`docker compose exec backend python -m pytest`), frontend `tsc --noEmit` exit 0.
- **Dev stack** — Docker Compose (postgres · redis · backend · celery · celery-beat · frontend) boots cleanly from `docker compose up -d`.
- **Fixtures + dev tooling** — seeded demo accounts + projects, `python manage.py simulate_inbound_email` for exercising the inbound email pipeline without a live mailbox.
- **Feedback surfaces** — Phase 1 AI thumbs on email classifications + suggested replies; Phase 1.5 per-feature widget on dashboard, project overview, email-organiser analysis panel. Both behind env-driven flags, exposed through `/api/auth/me/features`.

**Deliberately not blocking deploy** (postponed, tracked in [docs/plan.md](plan.md)):

- Customer-support tool (Chatwoot / Plain / Intercom) — per-feature widget covers user signal for v0.
- Phase 2 floating-button app feedback — waits on the support-tool decision.
- Per-project manager scoping (security #8 design) — only matters for multi-company tenancy.

## Ordered path to first production deploy

Every item has a "why" + a rough size. Items higher up unblock items below them.

### 1. Hosting decision — ✅ **Decided 2026-04-22**

**Render + Brevo + Cloudflare + Sentry + Render managed backups.** Rejected Fly.io / Scaleway / Hetzner from [hosting_plans.md](hosting_plans.md); Render's declarative Blueprint + managed Postgres with daily snapshots out-of-the-box + single-company-runnable simplicity won. Brevo covers both outbound SMTP and inbound email parsing in one account. Cloudflare in front gives DNS + TLS + WAF.

### 2. Production Docker image + CI pipeline — ✅ **Wired 2026-04-22**

- Backend Dockerfile already prod-ready (no changes).
- Frontend Dockerfile gained `ARG NEXT_PUBLIC_*` declarations in the `builder` stage so Render can bake the API/WS URLs into the JS bundle at build time.
- `backend-ci.yml` env mismatch fixed (Django reads `DB_*`, not `POSTGRES_*` / `DATABASE_URL`).
- `cd-production.yml` rewritten to the Render Deploy Hook pattern: `workflow_run` triggers on CI success on `main`, `curl`s the two per-service Deploy Hooks, polls `/api/docs/` for health. No external image registry needed — Render builds from the Dockerfiles in-repo.
- New [render.yaml](../render.yaml) Blueprint declares all 6 services in one file.

### 3. Database provisioning + migration runbook — ~1 day

- Managed Postgres on the chosen provider, network-scoped to the backend only.
- One-time: create DB, run `migrate`, decide whether to seed fixtures (probably not in prod; they're dev demo data).
- **Manager bootstrap problem** — manager self-signup lands `is_active=False` pending approval by an existing active manager. Document: create the first manager via Django admin shell (`createsuperuser`, then set `role=MANAGER, is_active=True`) so there's a human who can approve subsequent signups.

### 4. Secrets management — ~0.5 day

Required env vars in production:
- `DJANGO_SECRET_KEY` (50+ random chars)
- `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `DB_HOST`
- `INBOUND_EMAIL_WEBHOOK_SECRET` (generate with `openssl rand -hex 32`)
- `ANTHROPIC_API_KEY`
- `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (Textract OCR fallback)
- SMTP creds (`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`) — Postmark / Brevo / SendGrid per hosting choice
- `DJANGO_ALLOWED_HOSTS` (prod domain)
- `CORS_ALLOWED_ORIGINS` (frontend origin)
- `SENTRY_DSN` (optional but recommended)
- Feature flags: `FEATURE_AI_THUMBS`, `FEATURE_FEATURE_FEEDBACK` — probably `false` until a v0.2 rollout, but they're cheap to flip.

Each hosting option has a different secrets primitive — Fly secrets, Scaleway Secret Manager, Hetzner + Doppler / 1Password CLI. The content is identical; only the loading mechanism differs.

### 5. Inbound email webhook wiring — ~0.5 day

Backend code is done ([backend/email_organiser/views.py:200](../backend/email_organiser/views.py#L200), HMAC-verified via `X-Webhook-Secret`, rate-limited at 60/min, payload capped at 256 KB). What's left:
- DNS for `*@<your-domain>` routed to the provider's inbound parser (SES Inbound / SendGrid Inbound / Postmark Inbound — the chosen one matches the outbound provider).
- Provider webhook config pointing at `POST https://<domain>/api/webhooks/inbound-email/` with the secret in the `X-Webhook-Secret` header.
- End-to-end test: send an email to the project's `generic_email`, confirm the IncomingEmail row + classification run.

### 6. HTTPS / custom domain — ~0.5 day

- TLS cert (Let's Encrypt via the provider, or Cloudflare in front).
- Important because `REFRESH_COOKIE_SECURE=True` is the production default (see [backend/config/settings/base.py](../backend/config/settings/base.py)). Without TLS the cookie never sets and the auth flow breaks.
- Confirm `SECURE_SSL_REDIRECT=True` in [production.py](../backend/config/settings/production.py) works end-to-end.

### 7. CSP enforcement verification — ~0.5 day

CSP is already enforced in prod via [frontend/src/middleware.ts](../frontend/src/middleware.ts) (`script-src 'self'`, no `unsafe-inline`, no `unsafe-eval`). First-run check: log in, click every feature, open DevTools Console, confirm zero CSP violation reports. If any fire, they point at a real bug (some inline script that should be same-origin, or a third-party domain not in `connect-src`).

### 8. WebSocket in production — ~0.5 day

Dev stack runs Daphne via `docker compose`. Prod needs the reverse proxy to route `/ws/*` → Daphne (not just HTTP). Fly.io supports this natively; Scaleway / Hetzner may need a small nginx snippet. Verification: open the project chat, confirm "Live" badge appears (green WiFi icon in the chat header).

### 9. Celery worker + beat in production — ~0.5 day

Today the dev stack runs both as separate Compose services. Prod needs the same — one worker process + one beat process. Fly.io: two `processes` in `fly.toml`. Scaleway: two deployments. Hetzner: two systemd units or two Compose services behind the same image. Both share the Redis broker configured via `CELERY_BROKER_URL`.

### 10. Backup + observability — ~1 day

- Automated Postgres backups — every managed DB option has this built-in; confirm retention (≥ 7 days).
- Error tracking — Sentry DSN plumbing is already in place ([production.py](../backend/config/settings/production.py) checks `SENTRY_DSN`); set the env var to a project-specific DSN.
- Uptime monitoring — UptimeRobot or the provider's built-in; alert on a 2-minute downtime.
- Log aggregation — depends on the provider; even the provider's built-in log viewer is enough for v0.

### 11. First-customer onboarding flow — ~1 day

- Create the first manager manually (`createsuperuser` + set role/is_active).
- Pick a landing page strategy — the app today drops anonymous users at `/login`. If you want a marketing shell (`/`), decide: separate site (Framer / Webflow) vs a Next.js marketing route. Separate is faster.
- Prepare a 10-minute demo-data seed script for a fresh tenant, so the first customer's dashboard isn't empty on day one.

## What changes before first deploy

**Config / code touches:**

- [backend/config/settings/production.py](../backend/config/settings/production.py) — confirm `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True` are set (they are). No code changes expected.
- [docker-compose.yml](../docker-compose.yml) — dev-only; not deployed. Keep it for local dev; the production compose file is separate (or Fly.io's config replaces it entirely).
- **New:** `frontend/Dockerfile.prod` with `next build` + `next start` (or standalone output).
- **New:** `.github/workflows/ci.yml` with pytest + tsc + image build/push.
- **New:** Deploy manifest per provider (Fly's `fly.toml` / Scaleway serverless containers manifest / Hetzner Compose file).

**Zero code changes expected** for any of steps 3–11; they're environment + ops work.

## Recommended sequence for the next few sessions

1. ~~**Hosting decision**~~ — ✅ Render + Brevo + Cloudflare + Sentry (2026-04-22).
2. ~~**Production Dockerfile + CI**~~ — ✅ [render.yaml](../render.yaml) + CI fixes + CD rewrite (2026-04-22).
3. **Provision + first deploy** (1 live session) — follow [deploy_runbook.md §1](deploy_runbook.md). Render account → Blueprint apply → fill secrets → create first manager.
4. **Cloudflare DNS flip + env update** (0.5 session) — point domain at Render, update `DJANGO_ALLOWED_HOSTS` + `CORS_ALLOWED_ORIGINS` + `NEXT_PUBLIC_*`, verify WS works through Cloudflare proxy ([deploy_runbook.md §4](deploy_runbook.md)).
5. **Brevo inbound email wiring** (0.5 session) — domain verify + MX + webhook config ([deploy_runbook.md §5](deploy_runbook.md)).
6. **Tag `v0.1`** and start collecting real feedback through the widget.

## Offer for next session — superseded

(Was: draft hosting-agnostic Dockerfile + CI. Done in this session — see §2.)

## Pointers

- [docs/hosting_plans.md](hosting_plans.md) — three concrete hosting combos with price / residency / ops trade-offs.
- [docs/support-software-research.md](support-software-research.md) — Chatwoot / Plain / Intercom + n8n research (postponed decision).
- [docs/security.md](security.md) — security posture + finding #8 (per-project manager scoping) for when multi-tenancy becomes relevant.
- [docs/plan.md](plan.md) — living priority list; see the "Postponed" block for items explicitly not blocking deploy.
- [RUNNING.md](../RUNNING.md) — local dev instructions; useful reference for what prod needs to preserve (Daphne + Celery worker + beat).

# Production deploy runbook

Single-page ops reference. Open this before every deploy, and any time
something breaks in prod.

- **Hosting:** Render (web + worker + cron + managed Postgres + managed Key Value)
- **Email:** Brevo (outbound SMTP + inbound parsing)
- **DNS + TLS + edge:** Cloudflare in front of Render
- **Error tracking:** Sentry
- **Backups:** Render managed Postgres daily snapshots (7-day retention on Starter)
- **Blueprint:** [render.yaml](../render.yaml) at repo root

---

## 1. First-time setup (one-off)

Do these once, in order. After this the repo auto-deploys from `main`.

### 1.1 Brevo account

1. Sign up at https://app.brevo.com.
2. SMTP & API → `SMTP` tab → generate a new SMTP key (NOT your Brevo password — Brevo calls it "SMTP key").
3. Save `EMAIL_HOST_USER` (your account email) and `EMAIL_HOST_PASSWORD` (the SMTP key). You'll paste these into Render.
4. Leave "Inbound Parsing" for §5 below.

### 1.2 Sentry project

1. Sign up at https://sentry.io.
2. Create a Django project. Copy the DSN. You'll paste it into Render.

### 1.3 Render account + Blueprint apply

1. Sign up at https://render.com. Install the Render GitHub app on `Yrishe/Templating`.
2. Render dashboard → **New +** → **Blueprint** → select the repo → Render reads `render.yaml`.
3. Preview shows 6 resources: `contract-mgmt-backend` (web), `contract-mgmt-frontend` (web), `contract-mgmt-celery-worker` (worker), `contract-mgmt-celery-beat` (worker), `contract-mgmt-postgres` (db), `contract-mgmt-redis` (key-value). Approve.
4. Render provisions everything. Postgres + Redis come up first; app services come up once their dependencies are healthy. Expect ~5-10 min for the first apply.

### 1.4 Fill in the sync:false secrets

For each service with `sync: false` vars (the backend + the worker + the beat):

Render dashboard → service → **Environment** → for each of these keys, click "Add Environment Variable" and paste the value:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from https://console.anthropic.com/settings/keys |
| `SENTRY_DSN` | from §1.2 |
| `EMAIL_HOST_USER` | from §1.1 (your Brevo login email) |
| `EMAIL_HOST_PASSWORD` | from §1.1 (the SMTP key) |
| `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | optional; for Textract OCR fallback |

`DJANGO_SECRET_KEY` and `INBOUND_EMAIL_WEBHOOK_SECRET` are generated automatically (`generateValue: true` in the Blueprint). The latter is what you'll paste into Brevo's inbound webhook (§5.3). Grab it: Render → backend service → Environment → copy the generated value.

After filling secrets, each service redeploys once. Wait ~3 min.

### 1.5 GitHub secrets for CD

For each service on Render, **Settings → Deploy Hook** → copy URL.

Then on GitHub, **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `RENDER_DEPLOY_HOOK_BACKEND` | Deploy Hook URL of `contract-mgmt-backend` |
| `RENDER_DEPLOY_HOOK_FRONTEND` | Deploy Hook URL of `contract-mgmt-frontend` |

Then **Settings → Secrets and variables → Actions → Variables tab**:

| Variable | Value |
|---|---|
| `PRODUCTION_URL` | `https://contract-mgmt-backend.onrender.com` initially; update after DNS flip |

Create a GitHub Environment named `production` (Settings → Environments → New) with required reviewers if you want a manual approval gate before deploy. Optional.

### 1.6 First manager bootstrap

Manager self-signup lands `is_active=False` pending approval by an existing active manager. There is none yet — bootstrap one manually.

Render dashboard → backend service → **Shell** → run:

```bash
python manage.py createsuperuser
# email: you@yourdomain.com
# first name / last name: anything
# password: long random string
```

Then promote the user to manager role:

```bash
python manage.py shell -c "
from accounts.models import User
u = User.objects.get(email='you@yourdomain.com')
u.role = User.MANAGER
u.is_active = True
u.save()
print('ok:', u.email, u.role, u.is_active)
"
```

From now on, everyone else signs up via `/signup` and you approve manager signups via the Pending Managers page.

---

## 2. Every deploy

1. Open a PR. Backend CI + Frontend CI run automatically.
2. Merge to `main` when green.
3. `cd-production.yml` fires via `workflow_run` — hits both Render Deploy Hooks, then polls `/api/docs/` until it returns 200 (up to 10 min).
4. Watch the Render dashboard: backend turns yellow (deploying), then green (live). Worker + beat redeploy automatically because they share the backend Docker image.
5. Smoke-test the URLs from §7.

If CI is red → deploy does not fire. Fix the branch before merging.

---

## 3. Migrations

Django migrations run automatically at container start (the Dockerfile runs `collectstatic` + we rely on Django's `runserver`-equivalent behavior). For an emergency manual run:

```bash
# Render dashboard → backend service → Shell
python manage.py migrate
```

If you add a new migration that requires a one-off data backfill, gate the migration's `RunPython` on `allow_migrate` or run the backfill in a separate Render "Job" service post-deploy.

---

## 4. Cloudflare DNS + TLS

### 4.1 Point your domain at Render

In Cloudflare DNS:

| Type | Name | Target | Proxy |
|---|---|---|---|
| CNAME | `@` (or `www`) | `contract-mgmt-frontend.onrender.com` | orange cloud ON |
| CNAME | `api` | `contract-mgmt-backend.onrender.com` | orange cloud ON |

Then in Render → each service → **Settings → Custom Domains** → add the Cloudflare hostname (e.g. `app.yourdomain.com` for frontend, `api.yourdomain.com` for backend). Render issues a Let's Encrypt cert behind Cloudflare's own cert.

### 4.2 Update the backend's hostname env

Once DNS is live:

Render dashboard → `contract-mgmt-backend` → Environment → update:

- `DJANGO_ALLOWED_HOSTS=api.yourdomain.com`
- `CORS_ALLOWED_ORIGINS=https://app.yourdomain.com`

Then redeploy the backend service. Also update the frontend service's `NEXT_PUBLIC_API_URL=https://api.yourdomain.com` and `NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com`, and redeploy the frontend (the values are baked into the bundle at build time, so a redeploy is required for them to take effect).

### 4.3 WebSocket through Cloudflare — known gotcha

Cloudflare's free plan strips `Connection: Upgrade` on some edge nodes, breaking WebSocket. Render supports WS natively, but Cloudflare must not interfere.

Test: open a project chat, look for the "Live" badge (green Wi-Fi icon). If it stays on "Polling", try:

1. Cloudflare → DNS → `api` record → toggle proxy OFF (grey cloud). WS now goes direct to Render. Lose Cloudflare caching/WAF for the API subdomain but keep it for the app subdomain.
2. Or upgrade Cloudflare to Pro, where WebSocket is supported cleanly on the orange cloud.

---

## 5. Brevo inbound email wiring

Brevo parses incoming emails to `<project-slug>@<yourdomain>` and posts the parsed JSON to our webhook.

### 5.1 Verify the domain in Brevo

1. Brevo dashboard → **Senders, Domains & Dedicated IPs** → add `yourdomain.com`.
2. Brevo shows DNS records (SPF, DKIM). Add them in Cloudflare DNS.
3. Wait for verification (can take a few minutes).

### 5.2 Add MX record

Cloudflare DNS → add:

| Type | Name | Priority | Target |
|---|---|---|---|
| MX | `inbound` (or whatever subdomain you want) | 10 | `in.sendinblue.com` |

Brevo's MX target may differ — check the current value in Brevo's inbound parsing docs; `in.sendinblue.com` is the legacy address.

### 5.3 Configure inbound parsing webhook

Brevo dashboard → **Transactional → Settings → Incoming email**:

- **Webhook URL**: `https://api.yourdomain.com/api/webhooks/inbound-email/`
- **Header**: set a custom header `X-Webhook-Secret` with the value from Render's `INBOUND_EMAIL_WEBHOOK_SECRET` (grab from Render dashboard → backend → Environment → copy).
- **Domain to parse**: `inbound.yourdomain.com` (or whatever you set up in §5.2).

Test: send an email to any `<slug>@inbound.yourdomain.com`. Brevo parses, posts to the webhook, Django creates an `IncomingEmail` row (verify via Django admin or `simulate_inbound_email` command logs).

---

## 6. Backups

Render managed Postgres takes daily snapshots automatically on the Starter plan. Retention: 7 days.

### 6.1 On-demand backup before risky migration

Render dashboard → `contract-mgmt-postgres` → **Backups** → **Back up now**. Done.

### 6.2 Restore

Render dashboard → `contract-mgmt-postgres` → **Backups** → select snapshot → **Restore**. This overwrites the current DB. Confirm the warning — no undo.

### 6.3 Export for off-site storage

For belt-and-braces: periodically `render psql contract-mgmt-postgres` and `pg_dump` to a local file. Script later if needed.

---

## 7. Post-deploy smoke test

Run this checklist after every significant deploy. Takes ~5 min.

1. `curl -I https://api.yourdomain.com/api/docs/` → `HTTP 200`, `content-type: text/html`.
2. `curl -I https://app.yourdomain.com/` → `HTTP 307 → /login`.
3. Browser: visit `https://app.yourdomain.com/`. Log in as the bootstrap manager.
4. Dashboard renders. Click a project → overview renders → each tab (Chat, Contract, Change Requests, Timeline, Invite) opens without 404.
5. Chat tab: "Live" badge turns green (WebSocket).
6. DevTools → Application → Cookies: `refresh_token` has `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/api/auth/`.
7. DevTools → Console: no CSP violation reports.
8. Feature-feedback widget at the bottom of Dashboard + Project Overview: click thumbs-up → "Thanks for the feedback" appears (requires `FEATURE_FEATURE_FEEDBACK=true` in the Render env — off by default for v0, flip when you want real users rating features).
9. Sentry dashboard: no errors from the deploy window.
10. Send a test email to `<project>@inbound.yourdomain.com` → IncomingEmail row appears in Django admin within 30s.

Any failing step is a real issue — do not close the tab, capture the DevTools Network entry + the Render log + file a ticket. Don't attempt a "redeploy and hope" fix.

---

## 8. Rollback

Render dashboard → service → **Events** → pick the last known-good deploy → **Rollback**. Takes ~60s. DB is unaffected (migrations don't roll back automatically — if the deploy added a migration, you may need to manually revert it via `python manage.py migrate <app> <prev>` from the shell).

If the rollback also needs a DB rollback, use §6.2 to restore the snapshot taken before the deploy.

---

## 9. Where to look when things break

| Symptom | First place |
|---|---|
| App loads but API returns 500 | Render → `contract-mgmt-backend` → Logs; or Sentry issues |
| App shows "Cannot connect" | Cloudflare → Analytics → 5xx rate; or Render status page |
| WebSocket stays on "Polling" | §4.3 (Cloudflare WS strip) |
| Inbound emails not landing | Render backend logs for the webhook; Brevo delivery logs |
| Celery tasks not running | `contract-mgmt-celery-worker` logs; check Redis reachability |
| Scheduled task not firing | `contract-mgmt-celery-beat` logs; confirm beat process is alive |
| All manager signups stuck `is_active=False` | Log in as the bootstrap manager and approve via Pending Managers page |

Render's own status page: https://status.render.com. Don't waste time debugging if they're red.

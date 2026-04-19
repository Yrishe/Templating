# Hosting & Email Plans

Alternatives to AWS for (a) sending/receiving email and (b) hosting the app. Kept as a single doc because the two decisions tend to happen together and trade off against each other (EU-residency email pairs with EU-residency hosting, etc.).

**Current state:** [.env.example](../.env.example) assumes AWS SES (`EMAIL_BACKEND`, `AWS_SES_REGION_NAME`). Hosting is not yet committed — running under docker-compose locally; AWS was the default assumption before this review.

**Constraint that drives most of this:** the [email organiser](email_organiser.md) relies on *inbound* email via a webhook ([backend/email_organiser/views.py](../backend/email_organiser/views.py) `InboundEmailWebhookView`). Any email provider that doesn't offer inbound parsing is a non-starter for this app.

---

## Email alternatives

Ranked roughly by fit for our inbound-parsing use case.

| Provider | Pricing (rough) | Inbound | Region | Why pick |
|---|---|---|---|---|
| **Postmark** | ~$15/mo for 10k | ✅ Webhooks mirror SES shape | US; EU via Postmark EU | Best deliverability reputation; drop-in SES replacement |
| **Mailgun** | ~$15/mo start | ✅ Strongest routing rules | US + EU | Per-project inbound addresses map cleanly onto our routing |
| **SendGrid (Twilio)** | Free 100/day, $20+/mo | ✅ Inbound parse webhook | US | Biggest ecosystem; Twilio owns it |
| **Brevo** (ex-Sendinblue) | Free 300/day | ✅ | EU (France) | Cheapest option with EU data residency |
| **Scaleway TEM** | Usage-based, very low | ⚠️ Limited | EU (France) | Integrates naturally if hosting on Scaleway |
| **Resend** | Free 3k/mo | ⚠️ Limited/beta | US | Best DX; skip if organiser is core |
| Self-host (Postal, Haraka) | Infra cost only | ✅ Full control | Anywhere | Cheapest at scale; IP reputation burden + ops load |

**Key decision factor:** does the email organiser need to work against all inbound domains day one, or just our project sub-domains? Mailgun's routing rules shine for the former; Postmark/SendGrid are simpler for the latter.

---

## Hosting alternatives

Optimised for the actual workload: **Django + Celery workers + Celery beat + Redis + Postgres + Next.js**. Any option that can't run Celery workers cheaply is disqualified.

| Option | Strengths | Tradeoff | Fit |
|---|---|---|---|
| **Fly.io** | Docker-native, multi-region, managed Postgres, cheap per-machine workers | Smaller ecosystem than AWS; occasional regional capacity issues | ★★★★★ — matches our stack shape exactly |
| **Render** | Zero-ops, managed Postgres + Redis, static + web + worker in one dashboard | Slow cold starts on free tier; background-worker pricing adds up | ★★★★☆ |
| **Railway** | Best DX; push and go; usage-based | Costs scale faster than alternatives past hobby load | ★★★★☆ — nice for PoC, watch the bill |
| **DigitalOcean** (App Platform or Droplets + Managed DB) | Predictable pricing, mature managed Postgres/Redis | Less "magical" than Render/Fly | ★★★★☆ |
| **Hetzner** (VPS + Coolify/Dokku) | Cheapest by 3-5×; EU-based; raw power/€ | You operate the VPS; no managed services unless you add Neon/Supabase/Upstash | ★★★★☆ if you have ops time |
| **Scaleway** | EU residency; Kubernetes path when you scale; managed DB/Redis | Smaller region coverage | ★★★★☆ for GDPR-heavy users |
| **OVHcloud** | EU, enterprise-friendly | Dated DX | ★★★☆☆ |
| **Vercel** | For Next.js frontend only; best-in-class | Not a full backend host — pair with one of the above | Complementary |

**Not recommended:** Heroku (expensive per dyno, Celery-unfriendly pricing), pure Kubernetes (overkill at this scale).

---

## Recommended combos

Three coherent paths depending on what matters most.

### Combo 1 — minimal ops, fastest to ship
**Fly.io** (backend + Celery + Celery-beat + managed Postgres) + **Upstash Redis** (or Fly Redis addon) + **Vercel** (Next.js) + **Postmark** (email).
- Monthly cost at 5-user dev team scale: **~$30-60**.
- Single `fly.toml` per service; workers are just another Fly machine group.
- Postmark inbound webhook signatures match SES closely — minimal code change.
- Scales linearly to mid-5-figure MRR before you need to reconsider.

### Combo 2 — EU data residency (GDPR-priority)
**Scaleway** (Kapsule or serverless containers + Managed Postgres + Redis) + **Scaleway TEM** or **Brevo** (email) + **Vercel Pro** (Next.js, EU region) *or* Scaleway for everything.
- Monthly cost similar to Combo 1, slightly higher if you need Scaleway's higher tier.
- All data stays in Paris/Amsterdam.
- Email inbound is weaker on Scaleway TEM; Mailgun EU is the fallback if organiser needs richer routing.

### Combo 3 — cheapest at scale (more ops)
**Hetzner** (one or two Cloud VPS, e.g. CPX21 at ~€8/mo each) + **Coolify** or **Dokku** for compose-style deploys + **Neon/Supabase** (Postgres) or self-hosted + **Upstash** (Redis) + **Postmark** or **Mailgun** (email).
- Monthly cost: **~€20-30** even at modest production load.
- Requires someone who'll keep the VPS patched and backups running — not suitable if the team doesn't have that bandwidth.

---

## Decision framework

Pick the factor that matters most, then work backwards:

1. **Team has zero ops bandwidth** → Combo 1 (Fly.io + Vercel + Postmark).
2. **EU users / GDPR is existential** → Combo 2 (Scaleway + Brevo/Mailgun EU).
3. **Every euro matters and one person enjoys ops** → Combo 3 (Hetzner + Postmark).
4. **Unsure** → start with Combo 1; the migration cost from Fly to anything else is small because Docker Compose already describes the services.

---

## Decisions owed

- [ ] Hosting provider (default: Fly.io per Combo 1; revisit when first paying users land).
- [ ] Email provider (default: Postmark for drop-in SES replacement; Mailgun if organiser routing gets more complex).
- [ ] Postgres location — managed by hosting provider vs external (Neon, Supabase) vs self-hosted.
- [ ] Redis location — same question.
- [ ] Region — Frankfurt / Amsterdam / Paris for EU; us-east / us-west otherwise.

Each decision changes the others; lock the hosting pick first, then the rest falls into place.

---

## What this doesn't cover

- Object storage for contract PDFs (S3 alternatives: R2, Backblaze B2, Scaleway Object Storage) — call out once file storage becomes a cost line.
- CDN — Vercel covers Next.js; backend CDN only matters if we start serving signed download URLs heavily (post-security #4 that's the only endpoint that'd benefit).
- Observability (Sentry already in [config/settings/production.py](../backend/config/settings/production.py); log aggregation TBD — Axiom, Better Stack, or Grafana Cloud).

---

_Last updated: 2026-04-19._

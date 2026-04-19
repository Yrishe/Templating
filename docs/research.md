# Research & Feedback

How the team captures user feedback for product research. Adopted approach: **Plan A + Plan C** from the conversation on 2026-04-19.

- **Plan A (in-app feedback + AI thumbs)** — the always-on capture layer.
- **Plan C (structured research program)** — NPS, interview opt-in, quarterly cadence on top of Plan A.

No code yet; this document specifies what will be built so implementation can be scoped into tickets.

---

## Goals

1. Make "why did users do X?" answerable without scheduling a meeting.
2. Build a labelled dataset from AI-suggestion thumbs so the email-organiser pipeline can be evaluated and, later, fine-tuned.
3. Have a repeatable research rhythm (quarterly NPS + interviews) so decisions aren't driven by the loudest user in Slack.
4. Meet GDPR baseline from day one — consent, retention, deletion.

---

## Plan A — in-app feedback

### A.1 AI-suggestion thumbs

Every AI output gets a binary 👍 / 👎 plus an optional one-line reason. The feedback is tied to the specific suggestion it evaluates.

**Surface:**
- `EmailClassification` result in the email organiser — thumbs on the assigned label.
- `AiSuggestion` reply draft — thumbs on the draft itself.
- Any future AI feature — same component, same table.

**Backend — new model in a new `feedback` Django app:**

```python
class AISuggestionFeedback(models.Model):
    id           = UUIDField(primary_key=True)
    user         = FK(User, on_delete=PROTECT)
    project      = FK(Project, on_delete=CASCADE)
    target_type  = CharField(choices=[("classification", ...), ("suggestion", ...), ("timeline_event", ...)])
    target_id    = UUIDField()
    rating       = SmallIntegerField(choices=[(1, "up"), (-1, "down")])
    reason       = TextField(blank=True, max_length=500)
    model        = CharField(max_length=64)   # snapshot of ANTHROPIC_MODEL at time of rating
    provider     = CharField(max_length=32)   # "anthropic" / future providers (see docs/AI_API.md)
    created_at   = DateTimeField(auto_now_add=True)

    class Meta:
        indexes  = [Index(fields=["target_type", "target_id"]),
                    Index(fields=["project", "created_at"])]
        unique_together = [("user", "target_type", "target_id")]   # one vote per user per target
```

**API:** `POST /api/feedback/ai/` with body `{target_type, target_id, rating, reason?}`. Idempotent — re-posting updates the user's existing row.

**Frontend:** small component `<AiFeedback targetType targetId />` wrapping two icon buttons; clicking opens a one-line textarea for the optional reason and auto-submits after 3 s of idle. No modal.

### A.2 General app feedback widget

Always-available floating button ("Feedback") visible to authenticated users.

**Surface:** bottom-right floating button on every authenticated route. Clicking opens a side panel with:
- 1-5 rating (optional)
- Free text (required, max 2000 chars)
- Checkbox "You can contact me to follow up" (feeds Plan C's interview opt-in)
- Auto-captured context: current route, user id, role, app version, user agent, viewport. **Not** captured: DOM snapshot, screenshot, keystrokes. Explicit principle — we're measuring sentiment, not surveilling.

**Backend:**

```python
class AppFeedback(models.Model):
    id              = UUIDField(primary_key=True)
    user            = FK(User, on_delete=PROTECT)
    rating          = SmallIntegerField(null=True)   # 1-5, nullable
    body            = TextField(max_length=2000)
    route           = CharField(max_length=255)      # "/projects/<uuid>/contract"
    user_agent      = CharField(max_length=500)
    app_version     = CharField(max_length=32)       # NEXT_PUBLIC_APP_VERSION
    contact_consent = BooleanField(default=False)
    created_at      = DateTimeField(auto_now_add=True)
    triage_status   = CharField(default="new", choices=[("new", ...), ("reviewed", ...), ("actioned", ...), ("declined", ...)])
    triage_note     = TextField(blank=True)
```

**API:** `POST /api/feedback/app/`. Throttled at `10/minute/user` via `ScopedRateThrottle` (same pattern as the webhook throttle from security #11).

### A.3 Event routing

Every new `AppFeedback` row fires a webhook to the event bus (see [docs/support.md](support.md) for the n8n integration). Low-rated (≤2) app feedback pages the product Slack channel; 👎 AI feedback rolls into a daily digest instead of a live alert.

---

## Plan C — structured program

### C.1 Quarterly NPS

**Trigger:** Celery beat task `feedback.tasks.send_nps_survey` at `0 9 1 */3 *` (first day of each quarter, 09:00 UTC).
**Targets:** users active in the last 30 days, excluding those who received an NPS email in the last 90 days (enforced by a cooldown column on `User` or a dedicated `NpsInvite` log).
**Email:** plain-text link to a one-page Next.js form `/nps/<token>/` with a 0-10 slider + optional comment. Token is a signed JWT with 30-day TTL — no login required, single-use, tied to a `User` id at signing time.
**Data:**

```python
class NpsResponse(models.Model):
    user        = FK(User, on_delete=PROTECT)
    score       = SmallIntegerField()              # 0-10
    comment     = TextField(blank=True, max_length=1000)
    sent_at     = DateTimeField()                  # when the invite went out
    answered_at = DateTimeField(auto_now_add=True)
```

**Reporting:** `/api/feedback/nps/summary/` returns `{promoters, passives, detractors, nps, n}` per quarter; a simple dashboard card renders it. Managers see their own project's slice; admins see everything.

### C.2 Interview opt-in pipeline

**Source:** the `contact_consent` flag on `AppFeedback` (A.2) and a dedicated `ResearchConsent` row users can toggle in their profile ("Willing to be contacted for occasional 30-min interviews").

**Consent model:**

```python
class ResearchConsent(models.Model):
    user             = OneToOneField(User)
    consented        = BooleanField(default=False)
    consented_at     = DateTimeField(null=True)
    revoked_at       = DateTimeField(null=True)
    contact_preference = CharField(default="email", choices=[("email", ...), ("slack", ...)])
```

**Ops:** admin page `/admin/research/consent/` lists consented users with last-contacted date and a 90-day cooldown. Interview notes go into Notion (or wherever the research library lives) — **not** into this database. The app only tracks "contacted on YYYY-MM-DD for purpose X".

```python
class InterviewContact(models.Model):
    user       = FK(User, on_delete=PROTECT)
    contacted_at = DateTimeField(auto_now_add=True)
    topic      = CharField(max_length=120)
    notes_url  = URLField(blank=True)        # pointer to Notion/Drive page, not the notes themselves
```

### C.3 Research rhythm

Expected ops cadence, written down so the plan doesn't silently die:

| Cadence | Owner | Action |
|---|---|---|
| Weekly | PM | Triage `AppFeedback` queue (`triage_status="new"`) — 20-30 min. |
| Monthly | PM + eng | Review 👎 AI feedback sample (50 rows), tag failure modes. |
| Quarterly | PM | Send NPS, analyse results, draft interview question set. |
| Quarterly | PM | 4-6 interviews with consented users, write a one-page insight note. |

If no one owns "PM" yet, Plan C is dormant until that role exists — A.1 and A.2 still work standalone.

---

## Privacy & retention

- Feedback rows are **personal data**. Users can request deletion via a self-serve "Delete my feedback" button in their profile (future ticket); that wipes `AppFeedback`, `AISuggestionFeedback`, and `NpsResponse` rows tied to their id.
- Default retention: **24 months**, enforced by a monthly Celery task that soft-deletes older rows (keeps aggregate counts for quarterly reports).
- NPS / interview invite tokens are single-use and TTL'd at 30 days.
- No PII flows to the event bus (see [docs/support.md](support.md)) beyond the feedback text itself; the webhook payload is `{id, rating, triage_status, user_id}` — the body content stays inside the app.

See [REQUIREMENTS.md](../REQUIREMENTS.md) §6 for the broader compliance baseline.

---

## Security considerations

- Feedback endpoints authenticate via JWT like every other API route — no anonymous submissions.
- NPS link tokens: JWT signed with `DJANGO_SECRET_KEY`, `exp` = 30 days, `jti` stored in an `NpsInvite` row so reuse is detectable.
- Webhook out to n8n reuses the timing-safe comparison pattern from security finding #1 — secret goes in a single env var, compared with `hmac.compare_digest`.
- Rate limits: `10/minute/user` for app feedback POSTs, `30/minute/user` for AI thumbs (multiple classifications per screen).

---

## Implementation phases

**Phase 1 — Plan A.1 (AI thumbs)** · ~3 days
New `feedback` app + `AISuggestionFeedback` model + endpoint + `<AiFeedback>` React component + smoke tests. No consent/privacy UI yet (suggestion-level feedback is low-PII).

**Phase 2 — Plan A.2 (app feedback widget)** · ~3 days
`AppFeedback` model + endpoint + floating widget + triage view in Django admin. Route webhook to n8n per [docs/support.md](support.md). Ship behind a feature flag.

**Phase 3 — Plan C.1 (NPS)** · ~4 days
Beat task + invite email + tokenised page + summary endpoint + dashboard card.

**Phase 4 — Plan C.2 (interview opt-in)** · ~2 days
`ResearchConsent` toggle in profile + admin view + cooldown enforcement.

**Phase 5 — retention + deletion** · ~2 days
"Delete my feedback" self-serve button + monthly soft-delete task.

---

## Success metrics

If these numbers move, the program is working:

- **Widget response rate** — ≥ 5% of monthly active users submit app feedback.
- **AI thumbs volume** — ≥ 30% of AI suggestions get a thumb within 24h.
- **NPS answer rate** — ≥ 20% of invited users answer (industry benchmark ~15-25%).
- **Triage latency** — p90 `AppFeedback` goes from `new` → any other status within 7 days.
- **Action rate** — ≥ 1 ticket filed in Linear per 10 negative feedback rows.

If two of the five stall for a full quarter, the program needs redesign, not more features.

---

_Last updated: 2026-04-19._

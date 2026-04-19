# Backend Features

> Template. One section per feature / Django app capability. Delete the "Template" section once you add your first real entry.

Stack: Django 5 + DRF, Daphne (ASGI for HTTP + Channels), PostgreSQL 16, Redis 7, Celery workers + beat. Backend root: [backend/](../backend/).

---

## Feature: {{feature name}}

**Status:** {{proposed | in-progress | shipped}}
**Owner:** {{name}}
**Django app:** `{{app_label}}`

### Summary
One or two sentences describing the capability.

### Data model
- Model(s): `app/models.py :: ModelName`
- Notable fields / indexes / constraints
- Migration that introduced it: `app/migrations/XXXX_*.py`

### API endpoints
| Method | Path | View | Permission | Notes |
|---|---|---|---|---|
| GET | `/api/...` | `app.views.FooViewSet` | `IsAuthenticated` | paginated |

### Serializers
- Input: `app.serializers.FooCreateSerializer` — validates X, Y
- Output: `app.serializers.FooSerializer`

### Business logic
Where the rules live: service module, model method, signal, or Celery task.

### Async work
- Task: `app.tasks.do_foo` — triggered when, retries, idempotency key
- Schedule: beat entry in `config/celery.py`, if any

### Events / notifications emitted
`notifications` records created, websocket channels published to (`chat`).

### Tests
- `backend/app/tests/test_*.py` — coverage expectation
- Fixtures used

### Known gaps / TODO
- [ ] ...

---

## Feature: (next one)

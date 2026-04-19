# AI API Contract

Rules for integrating AI / LLM providers into this app. The goal is that **any caller (email organiser, chat, future features) depends on the contract here — never on a specific vendor SDK**. Swapping Anthropic for OpenAI, Azure OpenAI, a self-hosted model, or a local mock must be a single-file change: add an adapter, flip a setting.

Current state: there is one provider adapter (Anthropic) at `_call_claude()` in [backend/email_organiser/tasks.py](../backend/email_organiser/tasks.py). This document describes what to generalise *to* before adding a second provider — the pattern is captured here first so the refactor stays small.

---

## 1. Principles

1. **Thin, stable, vendor-neutral interface.** One function signature. Text in, text out. No provider-specific kwargs at the call site.
2. **Fail soft, never crash.** An unavailable provider (missing key, missing SDK, network error, 429, 5xx) returns `None`. Callers are expected to degrade — not retry in a tight loop.
3. **Stateless.** Each call carries its full context. No hidden conversation history, no client singleton that survives across tasks.
4. **Configurable at the `settings` boundary.** No hardcoded model names, base URLs, or keys in feature code.
5. **Observable.** Every call logs provider, model, duration, token usage (if the SDK returns it), and outcome.
6. **Cacheable where possible.** Prompt prefixes that don't change per request (classifier system prompt, schema examples) should be marked as cacheable when the provider supports it, so repeat calls are cheap.
7. **Auditable spend.** Every call is attributable to a feature + project; no cross-feature leaks.

---

## 2. The interface every provider must satisfy

```python
# backend/ai/providers/base.py (proposed)

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AIRequest:
    system_prompt: str
    user_message: str
    max_tokens: int = 1024
    temperature: float = 0.2
    response_format: str = "text"        # "text" | "json"
    cache_system_prompt: bool = False    # provider honors if it can
    feature: str = ""                    # "email_organiser.classify" — for telemetry
    project_id: str | None = None        # for cost attribution


@dataclass(frozen=True)
class AIResponse:
    text: str | None                     # None = failed/unavailable
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider: str = ""                   # "anthropic" / "openai" / ...
    model: str = ""                      # exact model string used
    cached: bool = False                 # prompt-cache hit?


class AIProvider(Protocol):
    name: str                            # "anthropic" | "openai" | ...

    def call(self, request: AIRequest) -> AIResponse:
        ...
```

Rules for implementations:

- **`text=None`** is the only failure signal. No raised exceptions leak out.
- **`json` responses** are still returned as strings — the caller parses. Providers should strip markdown fences if they add them.
- Adapters **must not retry silently**. One attempt per call. Retries belong in the Celery task layer with visible backoff.
- Timeout is **30 seconds max** unless the caller sets a longer `max_tokens` (in which case the adapter scales linearly with 1 second per 256 output tokens, capped at 120 s).

---

## 3. Provider selection

```python
# backend/ai/registry.py (proposed)

def get_provider(name: str | None = None) -> AIProvider:
    name = name or settings.AI_DEFAULT_PROVIDER
    return _REGISTRY[name]   # KeyError surfaces as ImproperlyConfigured at startup
```

Resolution order at each call site:

1. Explicit provider name passed in by the caller (rare; use for A/B tests).
2. `AI_PROVIDER_FOR_<FEATURE>` env var (e.g. `AI_PROVIDER_FOR_EMAIL_ORGANISER=openai`).
3. `AI_DEFAULT_PROVIDER` env var.
4. Settings file default (currently `"anthropic"`).

The registry is populated at import time. A missing provider key raises `ImproperlyConfigured` — same pattern as `_require_env()` in [config/settings/base.py](../backend/config/settings/base.py).

---

## 4. Configuration contract

Each provider declares its settings in one place. Example:

| Setting | Applies to | Default | Notes |
|---|---|---|---|
| `AI_DEFAULT_PROVIDER` | all | `"anthropic"` | must match a registered adapter |
| `AI_PROVIDER_FOR_EMAIL_ORGANISER` | email organiser only | unset | overrides the default |
| `ANTHROPIC_API_KEY` | anthropic | required | see finding #12 (docs/security.md) |
| `ANTHROPIC_MODEL` | anthropic | `"claude-sonnet-4-6"` | |
| `OPENAI_API_KEY` | openai | required | `_require_env()` when provider active |
| `OPENAI_MODEL` | openai | `"gpt-4.1-mini"` | |
| `OPENAI_BASE_URL` | openai | default | set for Azure OpenAI / proxy |
| `LOCAL_MODEL_URL` | local/ollama | required | `http://ollama:11434` in dev |

Rule: **only `_require_env()` the settings for the provider that is actually registered as active**. An unused provider's missing key must not block startup.

---

## 5. Observability

Every adapter logs exactly one structured line per call:

```
ai.call provider=<name> model=<str> feature=<str> project_id=<uuid|->
        input_tokens=<n|-> output_tokens=<n|-> duration_ms=<n>
        cached=<bool> outcome=<ok|error|timeout|rate_limited|unavailable>
```

Metrics (if Sentry / OTel is wired later): counter `ai_calls_total{provider,model,outcome}` and histogram `ai_call_duration_ms{provider,model}`.

---

## 6. Prompt conventions

- **System prompt = task description.** Never stuff per-request data into the system prompt — it should be byte-identical across calls of the same type so the provider's prompt cache can hit.
- **User message = per-request data.** Email body, project context, schema examples that depend on the current project.
- **Ask for strict JSON** when you need structure. Each feature owns a Pydantic / dataclass model and validates on the way back. Never `eval()` the response.
- **One shot, not chat.** No multi-turn. If the task genuinely needs follow-up, encode the full state in the next call.
- **Max-tokens is a hard budget.** Over-budget responses are truncated — the feature should degrade, not panic.

---

## 7. Failure handling at the caller

```python
response = ai.call(AIRequest(...))
if response.text is None:
    # degrade path — MUST be defined per feature
    return fallback_result()
parsed = _parse_json(response.text) or fallback_result()
```

Rule: every caller declares its **degrade path** up front. Acceptable degrades:
- Skip the classification (mark the email "needs manual review").
- Use a heuristic fallback (keyword match).
- Enqueue the task for a later retry with exponential backoff.

Unacceptable: raising to the user, marking the record "failed" with no retry, silent data loss.

---

## 8. Testing

- Every feature that uses `ai.call()` must have a test that passes `provider="mock"` and asserts the downstream behavior.
- `MockProvider` returns canned `AIResponse`s controllable via the test fixture (see pattern in [backend/tests/test_email_pipeline.py](../backend/tests/test_email_pipeline.py)).
- Tests **must not** hit a real provider. A CI run with `ANTHROPIC_API_KEY` unset should pass.

---

## 9. Where AI is currently called

| Feature | File | Purpose | Expected latency | Max tokens |
|---|---|---|---|---|
| Email classifier | [email_organiser/tasks.py](../backend/email_organiser/tasks.py) `_call_claude` (via `classify_email`) | Label inbound email (invoice / update / question / …) | <2 s | 512 |
| Topic analysis | same file, `analyse_topic` | Summarise thread topic + project relevance | <5 s | 2048 |
| Timeline generation | same file, `generate_timeline_event` | Convert email into a timeline entry | <2 s | 512 |

Each of these is a candidate for the new `ai.call(...)` interface when the refactor lands. None should embed provider-specific logic after that.

---

## 10. Adding a new provider — checklist

Use this section as a fill-in template when wiring a new adapter. Copy it to the bottom of the file; do not delete the existing provider entries.

```
## Provider: {{name}}

**Status:** proposed | implemented
**Adapter:** `backend/ai/providers/{{name}}.py`
**SDK dependency:** `{{pip package}}==`{{version}}
**Registry key:** `"{{name}}"`

### Settings introduced
- `{{NAME}}_API_KEY` (required when active)
- `{{NAME}}_MODEL` (default `"..."`)
- `{{NAME}}_BASE_URL` (optional)

### Capabilities
- [ ] JSON mode (native vs prompt-enforced)
- [ ] Prompt caching
- [ ] Streaming (unused today, document anyway)
- [ ] Per-call cost reporting via SDK response

### Not supported / known gaps
- …

### Test coverage added
- `backend/tests/test_ai_{{name}}.py`

### Rollout notes
- Flag: `AI_PROVIDER_FOR_<FEATURE>={{name}}` on {{date}}, default stays anthropic until {{date+2 weeks}}.
```

---

## Provider: anthropic

**Status:** implemented (pre-abstraction; will migrate when `backend/ai/` lands)
**Adapter (current):** `_call_claude()` in [backend/email_organiser/tasks.py](../backend/email_organiser/tasks.py)
**SDK:** `anthropic` (see [backend/requirements/base.txt](../backend/requirements/base.txt))
**Registry key:** `"anthropic"`

### Settings
- `ANTHROPIC_API_KEY` — required when active
- `ANTHROPIC_MODEL` — default `"claude-sonnet-4-6"`

### Capabilities
- JSON mode via prompt instruction (no native JSON-schema mode used).
- Prompt caching — available via the SDK's `cache_control` blocks; not yet opted into.
- Returns `input_tokens` and `output_tokens` per response; not yet logged.

### Gaps vs the contract
- No `AIResponse` wrapper — the adapter returns a bare `str | None`. Fix during the abstraction refactor.
- Telemetry line (section 5) not emitted — `logger.exception` only on error.
- Latency / token count not recorded.

### Test coverage
- [backend/tests/test_email_pipeline.py](../backend/tests/test_email_pipeline.py) (SDK is patched; real key never required).

---

_Last updated: 2026-04-19._

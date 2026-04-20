# Security #5 plan — HttpOnly refresh cookie + in-memory access token

**Status:** planned 2026-04-20. Implementation deferred to the next session. No code changes yet — this file exists so the next session can pick up cold.

## Context

[security.md #5](security.md#5) flags that both refresh and access tokens live in `sessionStorage` — readable by any script on the origin. An XSS anywhere in the frontend or a poisoned dependency exfiltrates both tokens in one line of JS. The production CSP is already tight (`script-src 'self'`, no `unsafe-inline`, no `unsafe-eval`), but that's a single layer; token-storage hardening is the second layer the review asked for.

The current architecture was a deliberate trade-off — per-tab `sessionStorage` lets Alice in tab 1 coexist with Bob in tab 2. **We're dropping that feature** (users can use Chrome profiles / incognito for the rare multi-session case) to take the security win.

## Decisions (locked in 2026-04-20)

1. **Refresh tokens** → `HttpOnly; Secure; SameSite=Strict` cookie, scoped to `/api/auth/`. No longer present in response bodies or JS-readable storage.
2. **Access tokens** → in-memory React ref only. Reload clears it; the app immediately calls the refresh endpoint (which reads the cookie) to mint a new one.
3. **Multi-tab different-users** → removed. Cookies are per-origin; whichever tab logs in last wins.
4. **CSP** → no changes. Already enforced in prod with the tightest useful policy; [security.md #5](security.md#5)'s "flip from Report-Only" note is stale and should be edited when the ticket lands.
5. **CSRF** → `SameSite=Strict` is the sole mitigation. Cross-site POSTs don't carry the cookie, so there's nothing to forge. No double-submit cookie or CSRF header needed.

## Backend

### Settings ([backend/config/settings/base.py](../backend/config/settings/base.py))

Add a small block near `SIMPLE_JWT`:

```python
# Refresh-token cookie (finding #5). HttpOnly keeps XSS from reading it,
# SameSite=Strict blocks cross-site CSRF, Path scoping means the cookie
# is only attached to /api/auth/ requests so the rest of the API surface
# never sees it. Max-Age matches SIMPLE_JWT.REFRESH_TOKEN_LIFETIME so the
# browser drops it at the same time the server stops honouring it.
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth/"
REFRESH_COOKIE_SAMESITE = "Strict"
REFRESH_COOKIE_MAX_AGE = int(SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
REFRESH_COOKIE_SECURE = True  # production default; dev override flips to False
```

- [development.py](../backend/config/settings/development.py): `REFRESH_COOKIE_SECURE = False` (local HTTP).
- [production.py](../backend/config/settings/production.py): no override needed.

### Views ([backend/accounts/views.py](../backend/accounts/views.py))

Add two tiny helpers at the top of the module:

```python
def _set_refresh_cookie(response, refresh_str: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_str,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )

def _clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
```

`_auth_payload(user, refresh)` returns `{user, access}` (no `refresh` in the body). Callers set the cookie on the response explicitly.

Changes per view:

- **LoginView / SignupView**: build the response with `{user, access}`, call `_set_refresh_cookie(response, str(refresh))`, return. Drop `refresh` from the body entirely.
- **TokenRefreshCookieView**: read from `request.COOKIES[settings.REFRESH_COOKIE_NAME]` (no body fallback — clean cut). 401 if missing. Rotate via `RefreshToken(raw)`. Set new cookie via `_set_refresh_cookie(response, str(refresh))`. Response body is `{access}` only.
- **LogoutView**: read the cookie; blacklist if present; clear the cookie on the response. Still `permissions.AllowAny` so an expired client can still trigger a clean logout.

### Auth class comment ([backend/accounts/authentication.py](../backend/accounts/authentication.py))

Update the docstring: cookies are now back in play **for the refresh token only**; access tokens still arrive via `Authorization: Bearer`. The class itself stays a no-op wrapper.

### Tests ([backend/tests/test_auth.py](../backend/tests/test_auth.py))

Invert `TestNoCookies` → `TestRefreshCookie` and update the signup/login/refresh tests. New coverage:

1. **Signup sets the refresh cookie** with `HttpOnly`, `Secure` (skip assert in dev), `SameSite=Strict`, `Path=/api/auth/`, `Max-Age` matching settings.
2. **Signup body contains `{user, access}`** — no `refresh` key.
3. **Login same as signup**.
4. **Refresh reads cookie** → 200 + new access in body + new cookie set.
5. **Refresh without cookie** → 401 (not 200).
6. **Refresh with body-only (legacy client)** → 401 (hard cut, no fallback).
7. **Logout clears the cookie** (response contains a `refresh_token` entry with empty value / Max-Age=0) and blacklists it.
8. **Rotation**: after a successful refresh, the old cookie value → 401.
9. **Cookie is `Path=/api/auth/` scoped** — assert via the cookie's `path` attribute on the Set-Cookie response.

Fixtures in conftest don't need to change; `APIClient` handles cookies automatically.

## Frontend

### In-memory access store ([frontend/src/lib/api.ts](../frontend/src/lib/api.ts))

Replace the `tokenStorage` object with a module-level ref:

```ts
// Access tokens live here — in the JS heap, not sessionStorage. XSS can
// still read this in the same tab, but:
//   1. the token has a 15-min TTL, and
//   2. the refresh token is in an HttpOnly cookie the attacker can't read,
// so the exfiltrated access alone buys at most a 15-min window, not a
// session they can renew.
let accessToken: string | null = null

export const accessTokenStore = {
  get: () => accessToken,
  set: (t: string) => { accessToken = t },
  clear: () => { accessToken = null },
}
```

Remove all `sessionStorage` references and the old `ACCESS_KEY` / `REFRESH_KEY` constants.

Update `buildFetchOptions` to read from `accessTokenStore.get()`.

Every `fetch` call gains `credentials: 'include'` so the browser attaches the refresh cookie to same-site requests. CORS is already configured with `CORS_ALLOW_CREDENTIALS=True`.

`tryRefreshToken()` no longer sends a body — it's a bare POST to `/api/auth/token/refresh/` that relies on the cookie. The response body is `{access}`; store it and return success.

### Auth context ([frontend/src/context/auth-context.tsx](../frontend/src/context/auth-context.tsx))

Bootstrap flow changes:

```ts
useEffect(() => {
  (async () => {
    // Every page load starts with no access token in memory. Ask the
    // refresh endpoint whether the browser still has a valid refresh
    // cookie; if yes, we're logged in. If not, show the login screen.
    const ok = await tryRefreshToken()
    if (ok) {
      try {
        const me = await api.get<User>('/api/auth/me/')
        setUser(me)
      } catch { setUser(null) }
    } else {
      setUser(null)
    }
    setIsLoading(false)
  })()
}, [])
```

`login` / `signup`: store `access` from the response body; cookie is set by the server. `logout`: call the endpoint (the cookie travels with it); clear in-memory access; server clears the cookie.

### Types ([frontend/src/types/index.ts](../frontend/src/types/index.ts))

Drop `refresh` from `AuthResponse`.

### Comments

Update the long explanatory block at the top of `api.ts` to reflect the new model (per-tab sessions are gone; see CHANGELOG). Keep it short — one paragraph.

## Docs + housekeeping

- [security.md](security.md): change finding #5 status to "Fixed YYYY-MM-DD" with a one-line summary.
- [CHANGELOG.md](../CHANGELOG.md): move the bullet from "parked" to "landed" under `## Unreleased`.
- [plan.md](plan.md): drop item #2 from the "Next session — pick one" list; item #3 (open decisions) remains queued.

## Verification

1. `docker compose up -d postgres redis`.
2. `cd backend && pytest tests/test_auth.py -v` — all green, including the inverted cookie tests.
3. `cd backend && pytest` — full suite green (baseline 116 tests; no regressions elsewhere).
4. `cd frontend && npm run type-check` — clean.
5. **Manual browser check** (the load-bearing test; unit tests can't catch cookie-attribute bugs):
   - Login; DevTools → Application → Cookies: `refresh_token` present with `HttpOnly`, `Secure` (prod only), `SameSite=Strict`, `Path=/api/auth/`.
   - DevTools Console: `document.cookie` does **not** list `refresh_token` (HttpOnly verification).
   - Network tab on login: response body has `access` but not `refresh`.
   - Reload the page: Network shows a POST to `/api/auth/token/refresh/` with the cookie attached; the app renders without requiring re-login.
   - Logout: cookie disappears from Application → Cookies.
   - Multi-tab: open a second tab, log in as a different user. The first tab will lose its session on the next refresh round-trip (expected — we gave this up).

## Files touched

**Modified:**

- `backend/accounts/views.py` — cookie helpers, LoginView/SignupView response reshape, TokenRefreshCookieView reads cookie, LogoutView reads+clears cookie
- `backend/accounts/authentication.py` — docstring
- `backend/config/settings/base.py` — `REFRESH_COOKIE_*` block
- `backend/config/settings/development.py` — `REFRESH_COOKIE_SECURE = False`
- `backend/tests/test_auth.py` — invert `TestNoCookies`; update login/signup/refresh/logout tests
- `frontend/src/lib/api.ts` — replace `tokenStorage` with `accessTokenStore`; add `credentials: 'include'`; refresh without body
- `frontend/src/context/auth-context.tsx` — bootstrap via refresh; in-memory access
- `frontend/src/types/index.ts` — drop `refresh` from `AuthResponse`
- `docs/security.md` — #5 status
- `CHANGELOG.md` — bullet moves from parked → landed
- `docs/plan.md` — drop item #2 from next-session list

**Created:** none.

## Explicit non-goals

- Not changing the CSP (already prod-enforced and tight enough).
- Not adding a CSRF token / double-submit cookie — `SameSite=Strict` is sufficient for our origin topology.
- Not preserving multi-tab different-users behaviour — explicitly dropped.
- Not returning refresh tokens in response bodies at all (no backwards-compat fallback for legacy clients — the frontend ships at the same time as the backend).
- Not changing access-token TTL (15 min stays).
- Not building a feature flag for this — it's a one-way migration, flags would only multiply the code paths.

from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Header-based JWT authentication for access tokens.

    Access tokens arrive via `Authorization: Bearer ...` and are held
    in memory on the client (finding #5). The refresh token does ride
    in an HttpOnly cookie, but that cookie is scoped to `/api/auth/`
    and read directly by `TokenRefreshCookieView` / `LogoutView` — this
    authentication class never touches it. Kept as a no-op subclass so
    we have a hook for request-level overrides later.
    """
    pass

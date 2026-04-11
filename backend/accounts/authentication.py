from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Header-based JWT authentication.

    The class name is kept for backwards compatibility with
    `DEFAULT_AUTHENTICATION_CLASSES` in settings, but cookies are no
    longer read. Since we switched to per-tab sessionStorage on the
    frontend (so multiple users can use the same browser in different
    tabs), the access token now arrives via `Authorization: Bearer ...`
    just like the default SimpleJWT behavior. This subclass is a no-op
    wrapper — kept as an extension point in case we need request-level
    overrides later.
    """
    pass

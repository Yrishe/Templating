from __future__ import annotations

from django.urls import path

from .views import (
    AccountDetailView,
    AccountListCreateView,
    LoginView,
    LogoutView,
    MeView,
    SignupView,
    TokenRefreshCookieView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshCookieView.as_view(), name="auth-token-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("accounts/", AccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<uuid:pk>/", AccountDetailView.as_view(), name="account-detail"),
]

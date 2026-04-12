from __future__ import annotations

from django.urls import path

from .views import (
    EmailAnalysisDetailView,
    EmailOrganiserDetailView,
    InboundEmailWebhookView,
    IncomingEmailDetailView,
    IncomingEmailListView,
    IncomingEmailReanalyseView,
    IncomingEmailResolveView,
    InvitedAccountListView,
    ProjectInviteView,
)

urlpatterns = [
    # Incoming emails — list, detail, resolve, re-analyse
    path(
        "projects/<uuid:project_id>/incoming-emails/",
        IncomingEmailListView.as_view(),
        name="incoming-email-list",
    ),
    path(
        "projects/<uuid:project_id>/incoming-emails/<uuid:pk>/",
        IncomingEmailDetailView.as_view(),
        name="incoming-email-detail",
    ),
    path(
        "projects/<uuid:project_id>/incoming-emails/<uuid:pk>/resolve/",
        IncomingEmailResolveView.as_view(),
        name="incoming-email-resolve",
    ),
    path(
        "projects/<uuid:project_id>/incoming-emails/<uuid:pk>/reanalyse/",
        IncomingEmailReanalyseView.as_view(),
        name="incoming-email-reanalyse",
    ),
    path(
        "projects/<uuid:project_id>/incoming-emails/<uuid:pk>/analysis/",
        EmailAnalysisDetailView.as_view(),
        name="email-analysis-detail",
    ),
    # Webhook
    path(
        "webhooks/inbound-email/",
        InboundEmailWebhookView.as_view(),
        name="inbound-email-webhook",
    ),
    # Email organiser config
    path(
        "email-organiser/<uuid:project_id>/",
        EmailOrganiserDetailView.as_view(),
        name="email-organiser-detail",
    ),
    # Invitations
    path(
        "projects/<uuid:project_id>/invite/",
        ProjectInviteView.as_view(),
        name="project-invite",
    ),
    path(
        "projects/<uuid:project_id>/invited-accounts/",
        InvitedAccountListView.as_view(),
        name="project-invited-accounts",
    ),
]

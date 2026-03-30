from __future__ import annotations

from django.urls import path

from .views import (
    EmailOrganiserDetailView,
    FinalResponseDetailView,
    FinalResponseListCreateView,
    FinalResponseSendView,
    InvitedAccountListView,
    ProjectInviteView,
)

urlpatterns = [
    path(
        "email-organiser/<uuid:project_id>/",
        EmailOrganiserDetailView.as_view(),
        name="email-organiser-detail",
    ),
    path(
        "email-organiser/<uuid:project_id>/final-responses/",
        FinalResponseListCreateView.as_view(),
        name="final-response-list-create",
    ),
    path(
        "email-organiser/<uuid:project_id>/final-responses/<uuid:pk>/",
        FinalResponseDetailView.as_view(),
        name="final-response-detail",
    ),
    path(
        "email-organiser/<uuid:project_id>/final-responses/<uuid:pk>/send/",
        FinalResponseSendView.as_view(),
        name="final-response-send",
    ),
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

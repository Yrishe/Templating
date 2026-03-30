from __future__ import annotations

from django.urls import path

from .views import (
    ProjectDetailView,
    ProjectListCreateView,
    ProjectMemberAddView,
    ProjectTimelineView,
    TimelineEventCreateView,
)

urlpatterns = [
    path("projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<uuid:project_id>/timeline/", ProjectTimelineView.as_view(), name="project-timeline"),
    path("projects/<uuid:project_id>/timeline/events/", TimelineEventCreateView.as_view(), name="timeline-event-create"),
    path("projects/<uuid:project_id>/members/", ProjectMemberAddView.as_view(), name="project-member-add"),
]

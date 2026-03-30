from __future__ import annotations

from django.urls import path

from .views import NotificationListView, NotificationMarkReadView, OutboundEmailListView

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("notifications/emails/", OutboundEmailListView.as_view(), name="outbound-email-list"),
]

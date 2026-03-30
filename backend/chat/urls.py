from __future__ import annotations

from django.urls import path

from .views import ChatDetailView, MessageListView

urlpatterns = [
    path("chats/<uuid:project_id>/", ChatDetailView.as_view(), name="chat-detail"),
    path("chats/<uuid:project_id>/messages/", MessageListView.as_view(), name="chat-messages"),
]

from __future__ import annotations

from django.urls import path

from .views import AISuggestionFeedbackView

urlpatterns = [
    path("feedback/ai/", AISuggestionFeedbackView.as_view(), name="ai-feedback"),
]

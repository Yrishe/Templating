from __future__ import annotations

from django.urls import path

from .views import AISuggestionFeedbackView, FeatureFeedbackView

urlpatterns = [
    path("feedback/ai/", AISuggestionFeedbackView.as_view(), name="ai-feedback"),
    path("feedback/feature/", FeatureFeedbackView.as_view(), name="feature-feedback"),
]

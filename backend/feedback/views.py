from __future__ import annotations

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import AISuggestionFeedback
from .serializers import AISuggestionFeedbackSerializer


def _visible_project_ids(user):
    """Project pks the given user is allowed to see.

    Mirrors the helper in notifications/views.py — managers have global
    oversight (see docs/security.md finding #8 for the parked per-manager
    scoping plan); other roles only see projects they have a
    ProjectMembership for.
    """
    from projects.models import Project, ProjectMembership

    if user.role == user.MANAGER:
        return Project.objects.values_list("pk", flat=True)
    return ProjectMembership.objects.filter(user=user).values_list(
        "project_id", flat=True
    )


def _resolve_target_project(target_type: str, target_id):
    """Return the Project an AI target belongs to, or None if the target is
    missing / unknown. Raises nothing — callers treat None as 404."""
    if target_type == AISuggestionFeedback.TARGET_CLASSIFICATION:
        from email_organiser.models import IncomingEmail

        try:
            email = IncomingEmail.objects.select_related("project").get(pk=target_id)
        except IncomingEmail.DoesNotExist:
            return None
        return email.project

    if target_type == AISuggestionFeedback.TARGET_SUGGESTION:
        from email_organiser.models import EmailAnalysis

        try:
            analysis = EmailAnalysis.objects.select_related("email__project").get(
                pk=target_id
            )
        except EmailAnalysis.DoesNotExist:
            return None
        return analysis.email.project

    # target_type == timeline_event is declared on the model for forward
    # compatibility but not wired this phase — the view short-circuits to
    # 400 before reaching this resolver.
    return None


class AISuggestionFeedbackView(APIView):
    """POST /api/feedback/ai/ — idempotent upsert of a user's 👍/👎 on an AI output."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_feedback"

    def post(self, request):
        serializer = AISuggestionFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_type = serializer.validated_data["target_type"]
        target_id = serializer.validated_data["target_id"]
        rating = serializer.validated_data["rating"]
        reason = serializer.validated_data.get("reason", "")

        # timeline_event is reserved for a future phase — reject politely
        # rather than silently 404'ing on a missing TimelineEvent.
        if target_type == AISuggestionFeedback.TARGET_TIMELINE_EVENT:
            return Response(
                {"target_type": ["timeline_event feedback is not yet supported."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = _resolve_target_project(target_type, target_id)
        if project is None:
            return Response(
                {"detail": "Target not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Permission boundary: the caller must have visibility on the
        # target's project. Return 404 (not 403) so the endpoint doesn't
        # leak the existence of cross-project targets.
        if project.pk not in set(_visible_project_ids(request.user)):
            return Response(
                {"detail": "Target not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Idempotent upsert — flips rating or attaches a reason on a
        # second POST. `model` is snapshotted on create only; subsequent
        # updates preserve the original snapshot so the dataset stays
        # readable after ANTHROPIC_MODEL changes.
        defaults = {
            "project": project,
            "rating": rating,
            "reason": reason,
        }
        obj, created = AISuggestionFeedback.objects.get_or_create(
            user=request.user,
            target_type=target_type,
            target_id=target_id,
            defaults={
                **defaults,
                "model": getattr(settings, "ANTHROPIC_MODEL", ""),
                "provider": "anthropic",
            },
        )
        if not created:
            obj.rating = rating
            obj.reason = reason
            obj.save(update_fields=["rating", "reason", "updated_at"])

        return Response(
            AISuggestionFeedbackSerializer(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

from __future__ import annotations

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsManager

from .models import Contract, ContractRequest
from .serializers import ContractRequestSerializer, ContractSerializer


class ContractListCreateView(generics.ListCreateAPIView):
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = []  # set per-request in get_parsers

    def get_parsers(self):
        from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
        if self.request is not None and self.request.method in ("POST",):
            return [MultiPartParser(), FormParser()]
        return [JSONParser()]

    def get_queryset(self):
        user = self.request.user
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        qs = Contract.objects.filter(project__in=member_project_ids).select_related("project", "created_by")
        # Honour `?project=` so the per-project Contract page only sees its own
        # contract — without this filter a fresh project would surface another
        # project's contract instead of the upload form.
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def create(self, request, *args, **kwargs):
        # Accounts upload contracts; managers can also create them
        if request.user.role not in (request.user.ACCOUNT, request.user.MANAGER):
            raise PermissionDenied("Only account users or managers can create contracts.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        contract = serializer.save()
        from notifications.tasks import create_contract_update_notification
        create_contract_update_notification.delay(str(contract.pk), "created")
        # Phase 3 (9): kick off PDF text extraction in the background so the
        # contract content is available for Claude's RAG context.
        if contract.file:
            from contracts.tasks import extract_contract_text
            extract_contract_text.delay(str(contract.pk))


class ContractDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        return Contract.objects.filter(project__in=member_project_ids).select_related("project", "created_by")

    def update(self, request, *args, **kwargs):
        if request.user.role != request.user.MANAGER:
            raise PermissionDenied("Only managers can edit contracts.")
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        contract = serializer.save()
        from notifications.tasks import create_contract_update_notification
        create_contract_update_notification.delay(str(contract.pk), "updated")
        # Re-extract text whenever the file changes
        if contract.file:
            from contracts.tasks import extract_contract_text
            extract_contract_text.delay(str(contract.pk))

    def get_parsers(self):
        # Support multipart for file uploads
        from rest_framework.parsers import FormParser, MultiPartParser
        if self.request is not None and self.request.method in ("PUT", "PATCH", "POST"):
            return [MultiPartParser(), FormParser()]
        return super().get_parsers()


class ContractActivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def post(self, request: Request, pk) -> Response:
        try:
            contract = Contract.objects.get(pk=pk)
        except Contract.DoesNotExist:
            return Response({"detail": "Contract not found."}, status=status.HTTP_404_NOT_FOUND)
        if contract.status == Contract.ACTIVE:
            return Response({"detail": "Contract is already active."}, status=status.HTTP_400_BAD_REQUEST)
        contract.status = Contract.ACTIVE
        contract.activated_at = timezone.now()
        contract.save(update_fields=["status", "activated_at"])

        # Notify project members of the activation
        from notifications.tasks import create_contract_update_notification
        create_contract_update_notification.delay(str(contract.pk), "activated")

        return Response(ContractSerializer(contract).data)


class ContractRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = ContractRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ContractRequest.objects.select_related("account", "project", "reviewed_by")
        if user.role == user.MANAGER:
            return qs.all()
        # Accounts see requests linked to their own account records
        return qs.filter(account__subscriber=user)

    def perform_create(self, serializer):
        cr = serializer.save()
        # Notify managers of the new contract request
        from notifications.tasks import create_contract_request_notification
        create_contract_request_notification.delay(str(cr.pk))


class ContractRequestDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ContractRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == user.MANAGER:
            return ContractRequest.objects.all()
        return ContractRequest.objects.filter(account__subscriber=user)


class ContractRequestApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def post(self, request: Request, pk) -> Response:
        try:
            cr = ContractRequest.objects.get(pk=pk)
        except ContractRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if cr.status != ContractRequest.PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)
        cr.status = ContractRequest.APPROVED
        cr.reviewed_by = request.user
        cr.reviewed_at = timezone.now()
        cr.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        # Auto-activate the project's contract
        try:
            contract = Contract.objects.get(project=cr.project)
            if contract.status == Contract.DRAFT:
                contract.status = Contract.ACTIVE
                contract.activated_at = timezone.now()
                contract.save(update_fields=["status", "activated_at"])
        except Contract.DoesNotExist:
            pass

        # Trigger notification async
        from notifications.tasks import create_contract_request_notification
        create_contract_request_notification.delay(str(cr.pk))
        return Response(ContractRequestSerializer(cr).data)


class ContractRequestRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def post(self, request: Request, pk) -> Response:
        try:
            cr = ContractRequest.objects.get(pk=pk)
        except ContractRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if cr.status != ContractRequest.PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)
        cr.status = ContractRequest.REJECTED
        cr.reviewed_by = request.user
        cr.reviewed_at = timezone.now()
        cr.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return Response(ContractRequestSerializer(cr).data)

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

    def get_queryset(self):
        user = self.request.user
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        return Contract.objects.filter(project__in=member_project_ids).select_related("project", "created_by")

    def create(self, request, *args, **kwargs):
        if request.user.role != request.user.MANAGER:
            raise PermissionDenied("Only managers can create contracts.")
        return super().create(request, *args, **kwargs)


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
        return Response(ContractSerializer(contract).data)


class ContractRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = ContractRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == user.MANAGER:
            return ContractRequest.objects.all().select_related("account", "project", "reviewed_by")
        # Subscribers see requests for their own accounts
        return ContractRequest.objects.filter(account__subscriber=user).select_related(
            "account", "project", "reviewed_by"
        )


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

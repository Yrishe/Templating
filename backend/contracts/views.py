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
        qs = Contract.objects.select_related("project", "created_by")
        # Managers see every project's contract (same oversight model as the
        # projects list). Accounts only see contracts for projects they're a
        # `ProjectMembership` on.
        if user.role != user.MANAGER:
            from projects.models import ProjectMembership
            member_project_ids = ProjectMembership.objects.filter(
                user=user
            ).values_list("project_id", flat=True)
            qs = qs.filter(project__in=member_project_ids)
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

        # Upsert semantics: `Contract.project` is a OneToOneField, so each
        # project can only ever have one row. The frontend decides POST vs
        # PATCH based on a cached read of `/api/contracts/?project=...`,
        # which can return empty for perfectly innocent reasons (cache miss,
        # stale cache after a Celery-side-effect 500, background
        # revalidation mid-click). When that happens the upload form POSTs,
        # and DRF's auto-generated UniqueValidator fails with
        # "contract with this project already exists." — a confusing UX for
        # what should be an idempotent "set the contract for this project"
        # action. Handle it server-side by delegating to an update when a
        # row already exists.
        project_id = request.data.get("project")
        if project_id:
            try:
                existing = Contract.objects.get(project_id=project_id)
            except Contract.DoesNotExist:
                pass
            else:
                serializer = self.get_serializer(existing, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                contract = serializer.save()
                from notifications.tasks import create_contract_update_notification
                create_contract_update_notification.delay(
                    str(contract.pk), "updated", str(request.user.pk)
                )
                if contract.file:
                    from contracts.tasks import extract_contract_text
                    extract_contract_text.delay(str(contract.pk))
                return Response(serializer.data, status=status.HTTP_200_OK)

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        contract = serializer.save()
        from notifications.tasks import create_contract_update_notification
        create_contract_update_notification.delay(
            str(contract.pk), "created", str(self.request.user.pk)
        )
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
        qs = Contract.objects.select_related("project", "created_by")
        if user.role != user.MANAGER:
            from projects.models import ProjectMembership
            member_project_ids = ProjectMembership.objects.filter(
                user=user
            ).values_list("project_id", flat=True)
            qs = qs.filter(project__in=member_project_ids)
        return qs

    def update(self, request, *args, **kwargs):
        # Accounts can replace their own contract (the upload form on the
        # Contract page shows an "Update contract" button for them), and
        # managers can edit any. Invited-account users (role=invited_account)
        # can only raise change requests, so they're denied here — the
        # frontend hides the upload form from them too.
        allowed = (request.user.MANAGER, request.user.ACCOUNT)
        if request.user.role not in allowed:
            raise PermissionDenied("Only accounts or managers can edit contracts.")
        # Additional membership gate: `get_queryset` already limits non-manager
        # users to contracts on projects they belong to, so the detail object
        # lookup returns 404 for outsiders before this point is even reached.
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        contract = serializer.save()
        from notifications.tasks import create_contract_update_notification
        create_contract_update_notification.delay(
            str(contract.pk), "updated", str(self.request.user.pk)
        )
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
        create_contract_update_notification.delay(
            str(contract.pk), "activated", str(request.user.pk)
        )

        return Response(ContractSerializer(contract).data)


class ContractRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = ContractRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_parsers(self):
        # POSTs are multipart so the optional `attachment` file can ride along
        # with the description; list GETs stay JSON.
        from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
        if self.request is not None and self.request.method == "POST":
            return [MultiPartParser(), FormParser(), JSONParser()]
        return [JSONParser()]

    def get_queryset(self):
        user = self.request.user
        qs = (
            ContractRequest.objects.select_related("account", "project", "reviewed_by")
            # Newest request first so the Change Requests history page and the
            # overview's pending-count stay in sync without client-side sort.
            .order_by("-created_at")
        )
        if user.role == user.MANAGER:
            qs = qs.all()
        else:
            # Accounts and invited accounts see requests for any project they
            # are a member of — filtering by account.subscriber would exclude
            # invited users who don't own an Account row.
            from projects.models import ProjectMembership
            member_project_ids = ProjectMembership.objects.filter(
                user=user
            ).values_list("project_id", flat=True)
            qs = qs.filter(project_id__in=member_project_ids)
        # Honour ?project= so per-project views only see their own requests
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        from projects.models import Project, ProjectMembership
        user = self.request.user

        # Rule 1: only Account-type users (creator or invited) may raise
        # contract requests. Managers approve them; they do not raise them.
        if user.role == user.MANAGER:
            raise PermissionDenied("Managers cannot raise contract requests.")

        project = serializer.validated_data.get("project")
        if project is None:
            raise PermissionDenied("project is required.")

        # Must be a member of the project — prevents cross-project submissions.
        if not ProjectMembership.objects.filter(project=project, user=user).exists():
            raise PermissionDenied("You are not a member of this project.")

        # account is server-assigned from the project's owning Account so the
        # manager's review queue stays keyed to the project regardless of
        # whether the raiser is the creator or an invited user.
        cr = serializer.save(account=project.account)

        from notifications.tasks import create_contract_request_notification
        create_contract_request_notification.delay(
            str(cr.pk), "raised", str(user.pk)
        )


class ContractRequestDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ContractRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == user.MANAGER:
            return ContractRequest.objects.all()
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(
            user=user
        ).values_list("project_id", flat=True)
        return ContractRequest.objects.filter(project_id__in=member_project_ids)


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
        cr.review_comment = (request.data.get("review_comment") or "").strip()
        cr.reviewed_by = request.user
        cr.reviewed_at = timezone.now()
        cr.save(update_fields=["status", "review_comment", "reviewed_by", "reviewed_at"])

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
        create_contract_request_notification.delay(
            str(cr.pk), "approved", str(request.user.pk)
        )
        return Response(ContractRequestSerializer(cr, context={"request": request}).data)


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
        cr.review_comment = (request.data.get("review_comment") or "").strip()
        cr.reviewed_by = request.user
        cr.reviewed_at = timezone.now()
        cr.save(update_fields=["status", "review_comment", "reviewed_by", "reviewed_at"])
        # Previously rejection was silent — everyone on the project should
        # know the request got turned down too.
        from notifications.tasks import create_contract_request_notification
        create_contract_request_notification.delay(
            str(cr.pk), "rejected", str(request.user.pk)
        )
        return Response(ContractRequestSerializer(cr, context={"request": request}).data)

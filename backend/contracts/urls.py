from __future__ import annotations

from django.urls import path

from .views import (
    ContractActivateView,
    ContractDetailView,
    ContractListCreateView,
    ContractRequestApproveView,
    ContractRequestDetailView,
    ContractRequestListCreateView,
    ContractRequestRejectView,
)

urlpatterns = [
    path("contracts/", ContractListCreateView.as_view(), name="contract-list-create"),
    path("contracts/<uuid:pk>/", ContractDetailView.as_view(), name="contract-detail"),
    path("contracts/<uuid:pk>/activate/", ContractActivateView.as_view(), name="contract-activate"),
    path("contract-requests/", ContractRequestListCreateView.as_view(), name="contract-request-list-create"),
    path("contract-requests/<uuid:pk>/", ContractRequestDetailView.as_view(), name="contract-request-detail"),
    path("contract-requests/<uuid:pk>/approve/", ContractRequestApproveView.as_view(), name="contract-request-approve"),
    path("contract-requests/<uuid:pk>/reject/", ContractRequestRejectView.as_view(), name="contract-request-reject"),
]

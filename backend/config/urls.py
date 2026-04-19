from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Application API endpoints
    path("api/auth/", include("accounts.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("contracts.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("chat.urls")),
    path("api/", include("email_organiser.urls")),
    path("api/", include("dashboard.urls")),
]

# Finding #4: never expose MEDIA_ROOT via public static() in production.
# Uploaded files are served by authenticated endpoints
# (ContractDownloadView / ContractRequestAttachmentView).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

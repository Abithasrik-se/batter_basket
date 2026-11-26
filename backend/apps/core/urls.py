from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, SettingsView, public_config

router = DefaultRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("public-config/", public_config),
    path("settings/", SettingsView.as_view()),
] + router.urls

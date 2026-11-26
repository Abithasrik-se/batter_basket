from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api import RBACPermission, RBACViewSetMixin
from apps.accounts.rbac import user_has_perm

from . import audit
from .models import AuditLog, SystemSettings
from .serializers import AuditLogSerializer, SystemSettingsSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def public_config(request):
    """What the login screen and theme loader need before anyone logs in."""
    s = SystemSettings.load()
    return Response(
        {
            "business_name": s.business_name,
            "default_language": s.default_language,
            "currency": s.currency,
            "theme": s.theme,
        }
    )


class SettingsView(APIView):
    """GET: any logged-in staff. PATCH: settings.manage only."""

    def get(self, request):
        return Response(SystemSettingsSerializer(SystemSettings.load()).data)

    def patch(self, request):
        if not user_has_perm(request.user, "settings.manage"):
            return Response({"detail": "Not allowed."}, status=403)
        obj = SystemSettings.load()
        before = SystemSettingsSerializer(obj).data
        ser = SystemSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record(request.user, "settings.update", obj, before=before, after=ser.data)
        return Response(ser.data)


class AuditLogViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    perm_read = "audit.view"
    location_field = None
    filterset_fields = ["action", "entity_type", "entity_id", "user"]

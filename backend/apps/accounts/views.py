from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit

from .api import AuditedMixin, RBACViewSetMixin
from .models import Membership, User
from .rbac import ROLE_LABELS, locations_with_perm, permissions_for, user_has_perm
from .serializers import MembershipSerializer, UserSerializer


def me_payload(user):
    perms = permissions_for(user)
    flat = sorted({p for plist in perms.values() for p in plist})
    return {
        "id": str(user.id),
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "preferred_language": user.preferred_language,
        "is_superuser": user.is_superuser,
        "roles": sorted({m.role for m in user.memberships.filter(is_active=True)}),
        "permissions": flat,
        "permissions_by_location": perms,
    }


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = None

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    def post(self, request):
        user = authenticate(request, username=request.data.get("username", ""), password=request.data.get("password", ""))
        if user is None or not user.is_active:
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        audit.record(user, "auth.login", user)
        return Response(me_payload(user))


class LogoutView(APIView):
    def post(self, request):
        audit.record(request.user, "auth.logout", request.user)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request.user))

    def patch(self, request):
        lang = request.data.get("preferred_language")
        if lang not in ("en", "ta"):
            return Response({"detail": "Unsupported language."}, status=400)
        request.user.preferred_language = lang
        request.user.save(update_fields=["preferred_language"])
        return Response(me_payload(request.user))


class ChangePasswordView(APIView):
    throttle_scope = "password"

    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get("old_password", "")):
            return Response({"detail": "Current password is incorrect."}, status=400)
        try:
            validate_password(request.data.get("new_password", ""), user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=400)
        user.set_password(request.data["new_password"])
        user.save()
        audit.record(user, "auth.password_change", user)
        return Response({"detail": "Password changed. Please log in again."})


class UserViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    """Staff accounts. Needs employees.manage; non-superusers only see users at their locations."""

    queryset = User.objects.filter(is_superuser=False).order_by("username")
    serializer_class = UserSerializer
    perm_read = "employees.view"
    perm_write = "employees.manage"
    location_field = None
    search_fields = ["username", "first_name", "last_name", "phone"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        locs = locations_with_perm(user, self.required_permission(self.request))
        return qs.filter(memberships__location__in=locs).distinct()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        audit.record(self.request.user, "user.deactivate", instance)


class MembershipViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Membership.objects.select_related("user", "location")
    serializer_class = MembershipSerializer
    perm_read = "employees.view"
    perm_write = "employees.manage"
    filterset_fields = ["user", "location", "role", "is_active"]

    def _check(self, serializer):
        role = serializer.validated_data.get("role")
        if role == "location_admin" and not self.request.user.is_superuser:
            raise PermissionDenied("Only the business owner can assign Location Admin.")

    def perform_create(self, serializer):
        self._check(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check(serializer)
        super().perform_update(serializer)


class RoleListView(APIView):
    def get(self, request):
        return Response([{"code": k, "label": v} for k, v in ROLE_LABELS.items()])

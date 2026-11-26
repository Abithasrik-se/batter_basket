"""Reusable DRF building blocks: permission class + view mixins.

Every ViewSet in the project declares:
    perm_read / perm_write   permission codes (see rbac.py)
    action_perms             per-action overrides, e.g. {"confirm": "orders.confirm"}
    location_field           ORM path to the location (None = not location scoped)
"""
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core import audit
from apps.core.exceptions import BusinessRuleError

from .rbac import locations_with_perm, user_has_perm


class RBACPermission(BasePermission):
    def has_permission(self, request, view):
        perm = view.required_permission(request)
        if perm is None:  # deny by default
            return False
        return user_has_perm(request.user, perm)


class RBACViewSetMixin:
    permission_classes = [RBACPermission]
    perm_read = None
    perm_write = None
    action_perms = {}
    location_field = "location"

    def required_permission(self, request):
        action = getattr(self, "action", None)
        if action in self.action_perms:
            return self.action_perms[action]
        return self.perm_read if request.method in SAFE_METHODS else self.perm_write

    def allowed_locations(self):
        return locations_with_perm(self.request.user, self.required_permission(self.request))

    def get_queryset(self):
        qs = super().get_queryset()
        if self.location_field:
            qs = qs.filter(**{f"{self.location_field}__in": self.allowed_locations()})
        return qs

    def assert_location_access(self, location, perm=None):
        perm = perm or self.required_permission(self.request)
        if not user_has_perm(self.request.user, perm, location):
            raise PermissionDenied("You do not have access to this location.")


class AuditedMixin:
    """Writes an AuditLog row for create / update / delete through the API."""

    audit_prefix = None

    def _prefix(self):
        return self.audit_prefix or self.queryset.model.__name__.lower()

    def perform_create(self, serializer):
        loc = serializer.validated_data.get("location")
        if loc is not None and hasattr(self, "assert_location_access"):
            self.assert_location_access(loc)
        instance = serializer.save()
        audit.record(self.request.user, f"{self._prefix()}.create", instance, after=self.get_serializer(instance).data)

    def perform_update(self, serializer):
        before = self.get_serializer(serializer.instance).data
        loc = serializer.validated_data.get("location")
        if loc is not None and hasattr(self, "assert_location_access"):
            self.assert_location_access(loc)
        instance = serializer.save()
        audit.record(self.request.user, f"{self._prefix()}.update", instance, before=before, after=self.get_serializer(instance).data)

    def perform_destroy(self, instance):
        """Hard delete only when nothing else depends on the record; otherwise explain how to proceed."""
        before = self.get_serializer(instance).data
        try:
            with transaction.atomic():
                audit.record(self.request.user, f"{self._prefix()}.delete", instance, before=before)
                instance.delete()
        except (ProtectedError, RestrictedError):
            raise BusinessRuleError("This record is used by other records (orders, stock, invoices...) so it cannot be deleted. Mark it inactive instead.")

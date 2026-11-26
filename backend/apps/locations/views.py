from rest_framework import viewsets

from apps.accounts.api import AuditedMixin, RBACViewSetMixin
from apps.core import audit

from .models import Location
from .serializers import LocationSerializer


class LocationViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    perm_read = "locations.view"
    perm_write = "locations.manage"
    location_field = "pk"  # a user only sees locations where they hold the role
    search_fields = ["name", "code"]
    filterset_fields = ["is_active"]

    def perform_destroy(self, instance):
        """Locations are deactivated, never deleted."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        audit.record(self.request.user, "location.deactivate", instance)

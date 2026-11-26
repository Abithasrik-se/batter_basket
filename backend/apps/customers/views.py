from rest_framework import viewsets

from apps.accounts.api import AuditedMixin, RBACViewSetMixin

from .models import Customer, CustomerAddress
from .serializers import CustomerAddressSerializer, CustomerSerializer


class CustomerViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    """Customers are shared by the whole business (not location scoped)."""

    queryset = Customer.objects.prefetch_related("addresses")
    serializer_class = CustomerSerializer
    perm_read = "customers.view"
    perm_write = "customers.manage"
    location_field = None
    search_fields = ["name", "phone", "email"]
    filterset_fields = ["category", "price_group", "is_active"]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class CustomerAddressViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = CustomerAddress.objects.all()
    serializer_class = CustomerAddressSerializer
    perm_read = "customers.view"
    perm_write = "customers.manage"
    location_field = None
    filterset_fields = ["customer"]

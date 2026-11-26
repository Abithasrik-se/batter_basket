from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import AuditedMixin, RBACViewSetMixin

from . import services
from .models import Purchase, Supplier
from .serializers import PurchaseSerializer, SupplierPaymentSerializer, SupplierSerializer


class SupplierViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    perm_read = "purchasing.view"
    perm_write = "purchasing.create"
    location_field = None
    search_fields = ["name", "phone"]
    filterset_fields = ["is_active"]


class PurchaseViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    """Purchases are created via the service (stock only moves on `receive`). No edit/delete."""

    queryset = Purchase.objects.select_related("supplier", "location").prefetch_related("lines__raw_material", "payments")
    serializer_class = PurchaseSerializer
    perm_read = "purchasing.view"
    perm_write = "purchasing.create"
    action_perms = {"receive": "purchasing.create", "pay": "purchasing.pay"}
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["supplier", "location", "status"]
    search_fields = ["invoice_number", "supplier__name"]

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["location"])
        purchase = services.create_purchase(user=request.user, supplier=d["supplier"], location=d["location"], purchase_date=d["purchase_date"], lines=d["lines"], invoice_number=d.get("invoice_number", ""))
        return Response(self.get_serializer(purchase).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        purchase = self.get_object()
        ser = self.get_serializer(purchase, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d.get("location"):
            self.assert_location_access(d["location"])
        purchase = services.update_purchase(purchase, request.user, **{k: d.get(k) for k in ("supplier", "location", "purchase_date", "invoice_number", "lines")})
        return Response(self.get_serializer(purchase).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_purchase(self.get_object(), request.user)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        purchase = services.receive_purchase(self.get_object(), request.user)
        return Response(self.get_serializer(purchase).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        purchase = self.get_object()
        ser = SupplierPaymentSerializer(data={**request.data, "purchase": purchase.pk})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        pay = services.pay_supplier(purchase, amount=d["amount"], method=d["method"], paid_on=d["paid_on"], reference=d.get("reference", ""), user=request.user)
        return Response(SupplierPaymentSerializer(pay).data, status=201)

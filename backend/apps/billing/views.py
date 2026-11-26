from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import RBACViewSetMixin

from . import services
from .models import CashClosing, Invoice, Payment
from .serializers import (CashClosingSerializer, InvoiceSerializer, PaymentSerializer, RecordPaymentSerializer,
                          RefundInputSerializer, RefundSerializer)


class InvoiceViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.select_related("customer", "order", "location")
    serializer_class = InvoiceSerializer
    perm_read = "billing.view"
    filterset_fields = ["location", "customer", "invoice_type"]
    search_fields = ["invoice_number", "customer__name", "order__order_number"]

    @action(detail=True, methods=["get"])
    def print(self, request, pk=None):
        """Printable bill (browser Print -> A4, or 'Save as PDF')."""
        from apps.core.models import SystemSettings

        from . import render as r

        inv = self.get_object()
        cfg = SystemSettings.load()
        lines = list(inv.order.lines.select_related("package__product"))
        outstanding = services.invoice_outstanding(inv)
        ctx = {
            "inv": inv, "cfg": cfg, "lines": lines, "paid": services.paid_amount(inv), "outstanding": outstanding,
            "payments": inv.payments.all(), "words": r.amount_in_words(inv.total - inv.credit_total), "hsn": r.hsn_summary(lines),
            "qr": r.upi_qr_svg(cfg.upi_id, inv.business_name, outstanding, inv.invoice_number) if outstanding > 0 else "",
            "address": inv.order.delivery_address, "gst": inv.invoice_type == "tax_invoice",
        }
        return render(request, "billing/receipt.html", ctx)


class PaymentViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Payments are record-only: POST /payments/record/, POST /payments/{id}/refund/. No edit or delete."""

    queryset = Payment.objects.select_related("invoice", "invoice__customer")
    serializer_class = PaymentSerializer
    perm_read = "payments.view"
    location_field = "invoice__location"
    action_perms = {"record": "payments.record", "refund": "payments.refund"}
    filterset_fields = ["method", "invoice", "invoice__location"]

    @action(detail=False, methods=["post"])
    def record(self, request):
        ser = RecordPaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["invoice"].location)
        p = services.record_payment(d["invoice"], method=d["method"], amount=d["amount"], tender=d.get("tender_amount"), reference=d["reference"], user=request.user)
        return Response(PaymentSerializer(p).data, status=201)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        payment = self.get_object()
        ser = RefundInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        r = services.refund_payment(payment, amount=ser.validated_data["amount"], reason=ser.validated_data["reason"], user=request.user)
        return Response(RefundSerializer(r).data, status=201)


class CashClosingViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    queryset = CashClosing.objects.select_related("location")
    serializer_class = CashClosingSerializer
    perm_read = "payments.view"
    perm_write = "cash.close"
    http_method_names = ["get", "post", "head", "options"]
    action_perms = {"expected": "payments.view"}
    filterset_fields = ["location", "date"]

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["location"])
        c = services.close_cash(d["location"], d["date"], d["counted_cash"], request.user, d.get("notes", ""))
        return Response(self.get_serializer(c).data, status=201)

    @action(detail=False, methods=["get"])
    def expected(self, request):
        from apps.locations.models import Location

        loc = Location.objects.filter(pk=request.query_params.get("location")).first()
        if not loc:
            return Response({"detail": "location is required"}, status=400)
        self.assert_location_access(loc, "payments.view")
        return Response({"expected_cash": str(services.expected_cash(loc, request.query_params.get("date")))})

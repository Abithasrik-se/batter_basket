from rest_framework import serializers

from .models import CashClosing, Invoice, Payment, Refund
from .services import invoice_outstanding, paid_amount


class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    paid = serializers.SerializerMethodField()
    outstanding = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["id", "invoice_number", "invoice_type", "order", "order_number", "customer", "customer_name", "location", "issued_at", "gross_total", "discount_total", "taxable_total", "cgst", "sgst", "delivery_fee", "total", "credit_total", "paid", "outstanding"]

    def get_paid(self, obj):
        return str(paid_amount(obj))

    def get_outstanding(self, obj):
        return str(invoice_outstanding(obj))


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "invoice", "method", "amount", "tender_amount", "change_returned", "reference", "received_by", "received_at"]
        read_only_fields = ["change_returned", "received_by", "received_at"]


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ["id", "payment", "amount", "reason", "refunded_by", "refunded_at"]


class RecordPaymentSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    method = serializers.ChoiceField(choices=["cash", "upi", "bank", "gateway"])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    tender_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True, default="")


class RefundInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()


class CashClosingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashClosing
        fields = ["id", "location", "date", "expected_cash", "counted_cash", "difference", "notes", "closed_by", "created_at"]
        read_only_fields = ["expected_cash", "difference", "closed_by", "created_at"]

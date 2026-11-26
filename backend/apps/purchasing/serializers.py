from rest_framework import serializers

from .models import Purchase, PurchaseLine, Supplier, SupplierPayment


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "email", "address", "gstin", "is_active"]


class PurchaseLineSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)

    class Meta:
        model = PurchaseLine
        fields = ["id", "raw_material", "raw_material_name", "quantity", "unit_cost", "line_total"]
        read_only_fields = ["line_total"]


class PurchaseSerializer(serializers.ModelSerializer):
    lines = PurchaseLineSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = Purchase
        fields = ["id", "supplier", "supplier_name", "location", "invoice_number", "purchase_date", "status", "total", "paid_amount", "balance", "payment_status", "lines"]
        read_only_fields = ["status", "total"]


class SupplierPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPayment
        fields = ["id", "purchase", "amount", "method", "paid_on", "reference", "created_at"]
        read_only_fields = ["created_at"]

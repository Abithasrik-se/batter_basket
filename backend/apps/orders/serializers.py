from rest_framework import serializers

from apps.catalog.models import Package
from apps.customers.models import Customer, CustomerAddress
from apps.locations.models import Location

from .models import Order, OrderLine, OrderStatusHistory


class OrderLineSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.__str__", read_only=True)

    class Meta:
        model = OrderLine
        fields = ["id", "package", "package_name", "quantity", "free_quantity", "unit_price", "discount_amount", "tax_rate", "taxable_amount", "tax_amount", "line_total", "returned_quantity"]


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ["from_status", "to_status", "note", "changed_by", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "order_number", "customer", "customer_name", "location", "location_name", "source", "status", "payment_status", "delivery_address", "delivery_instructions", "scheduled_date", "coupon_code", "gross_total", "discount_total", "taxable_total", "tax_total", "delivery_fee", "delivery_distance_km", "delivery_fee_detail", "total", "created_at", "lines", "history"]
        read_only_fields = ["order_number", "customer", "location", "source", "status", "payment_status", "coupon_code", "gross_total", "discount_total", "taxable_total", "tax_total", "delivery_fee", "delivery_distance_km", "delivery_fee_detail", "total", "created_at"]


class OrderLineInputSerializer(serializers.Serializer):
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.select_related("product"))
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    lines = OrderLineInputSerializer(many=True)
    source = serializers.ChoiceField(choices=["admin", "website", "pwa"], default="admin")
    delivery_address = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.all())  # mandatory
    delivery_instructions = serializers.CharField(required=False, allow_blank=True, default="")
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    scheduled_date = serializers.DateField(required=False)


class OrderUpdateSerializer(serializers.Serializer):
    lines = OrderLineInputSerializer(many=True, required=False)
    delivery_address = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.all(), required=False)
    delivery_instructions = serializers.CharField(required=False, allow_blank=True)
    scheduled_date = serializers.DateField(required=False)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ReturnSerializer(serializers.Serializer):
    reason = serializers.CharField()
    restock = serializers.BooleanField(default=False)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)

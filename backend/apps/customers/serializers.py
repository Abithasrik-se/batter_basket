from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import serializers

from .models import Customer, CustomerAddress


class CustomerAddressSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = CustomerAddress
        fields = ["id", "customer", "customer_name", "label", "address_line", "area", "pincode", "latitude", "longitude", "is_default"]


class CustomerSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)
    outstanding = serializers.SerializerMethodField()
    # optional first address, saved together with the customer
    address_line = serializers.CharField(write_only=True, required=False, allow_blank=True)
    pincode = serializers.CharField(write_only=True, required=False, allow_blank=True)
    address_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False, allow_null=True)
    address_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False, allow_null=True)

    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "email", "category", "price_group", "discount_percent", "gstin", "credit_limit", "preferred_location", "latitude", "longitude", "notes", "notifications_opt_in", "marketing_opt_in", "loyalty_points", "is_active", "addresses", "outstanding", "address_line", "pincode", "address_latitude", "address_longitude"]
        read_only_fields = ["loyalty_points"]

    def create(self, validated):
        line = validated.pop("address_line", "").strip()
        pin = validated.pop("pincode", "")
        lat, lng = validated.pop("address_latitude", None), validated.pop("address_longitude", None)
        customer = super().create(validated)
        if line:
            CustomerAddress.objects.create(customer=customer, label="Home", address_line=line, pincode=pin, latitude=lat, longitude=lng, is_default=True)
        return customer

    def get_outstanding(self, obj):
        from apps.billing.services import customer_outstanding

        return str(customer_outstanding(obj))

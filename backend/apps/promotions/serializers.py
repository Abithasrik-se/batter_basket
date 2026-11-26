from rest_framework import serializers

from .models import Coupon, LoyaltyEntry, Promotion


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ["id", "name", "package", "buy_quantity", "free_quantity", "valid_from", "valid_to", "is_active"]


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["id", "code", "discount_percent", "min_order_total", "max_uses", "per_customer_limit", "valid_from", "valid_to", "is_active"]


class LoyaltyEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyEntry
        fields = ["id", "customer", "points", "reason", "order", "note", "created_at"]

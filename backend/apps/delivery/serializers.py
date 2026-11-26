from rest_framework import serializers

from .models import DeliveryAssignment, DeliveryRecord, LocationPing


class DeliveryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = ["id", "assignment", "outcome", "failed_reason", "customer_confirmed", "proof_note", "latitude", "longitude", "recorded_by", "supersedes", "correction_reason", "created_at"]


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_total = serializers.DecimalField(source="order.total", max_digits=12, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(source="order.payment_status", read_only=True)
    customer_name = serializers.CharField(source="order.customer.name", read_only=True)
    customer_phone = serializers.CharField(source="order.customer.phone", read_only=True)
    address = serializers.SerializerMethodField()
    navigation_url = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source="employee.username", read_only=True)
    records = DeliveryRecordSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryAssignment
        fields = ["id", "order", "order_number", "order_total", "payment_status", "location", "employee", "employee_name", "route_sequence", "status", "customer_name", "customer_phone", "address", "navigation_url", "records"]

    def _addr(self, obj):
        return obj.order.delivery_address

    def get_address(self, obj):
        a = self._addr(obj)
        return a.address_line if a else ""

    def get_navigation_url(self, obj):
        a = self._addr(obj)
        c = obj.order.customer
        lat, lng = (a.latitude, a.longitude) if a and a.latitude is not None else (c.latitude, c.longitude)
        if lat is not None and lng is not None:
            return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        if a:
            from urllib.parse import quote

            return f"https://www.google.com/maps/dir/?api=1&destination={quote(a.address_line)}"
        return ""


class LocationPingSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationPing
        fields = ["latitude", "longitude", "accuracy_m", "recorded_at"]


from rest_framework import serializers as _s  # noqa: E402

from .models import DeliveryFeeSlab, SurgeRule  # noqa: E402


class DeliveryFeeSlabSerializer(_s.ModelSerializer):
    location_name = _s.CharField(source="location.name", read_only=True)

    class Meta:
        model = DeliveryFeeSlab
        fields = ["id", "location", "location_name", "label", "min_km", "max_km", "base_fee", "per_km_fee", "is_active"]

    def validate(self, attrs):
        loc = attrs.get("location") or self.instance.location
        lo = attrs.get("min_km", getattr(self.instance, "min_km", 0))
        hi = attrs.get("max_km", getattr(self.instance, "max_km", None))
        if hi is not None and hi <= lo:
            raise _s.ValidationError("Max km must be greater than min km.")
        others = DeliveryFeeSlab.objects.filter(location=loc, is_active=True)
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        if attrs.get("is_active", True):
            for o in others:
                o_hi = o.max_km if o.max_km is not None else 10**9
                n_hi = hi if hi is not None else 10**9
                if lo < o_hi and o.min_km < n_hi:
                    raise _s.ValidationError(f"This distance range overlaps an existing slab ({o.min_km} to {o.max_km or 'beyond'} km).")
        return attrs


class SurgeRuleSerializer(_s.ModelSerializer):
    location_name = _s.CharField(source="location.name", read_only=True)

    class Meta:
        model = SurgeRule
        fields = ["id", "location", "location_name", "label", "min_orders", "surcharge_type", "value", "is_active"]

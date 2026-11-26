from rest_framework import serializers

from apps.locations.models import Location

from .models import RawMaterial, StockBucket, StockMovement, StockTransfer


class RawMaterialSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = RawMaterial
        fields = ["id", "name", "name_ta", "unit", "unit_code", "min_stock", "is_packaging", "is_active"]


class StockBucketSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    item_name = serializers.CharField(read_only=True)
    unit_code = serializers.CharField(read_only=True)
    available = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True, default=None)

    class Meta:
        model = StockBucket
        fields = ["id", "location", "location_name", "kind", "item_name", "unit_code", "batch", "batch_number", "expiry_date", "quantity", "reserved", "available"]


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="bucket.item_name", read_only=True)
    location_name = serializers.CharField(source="bucket.location.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "created_at", "bucket", "item_name", "location_name", "movement_type", "quantity_delta", "balance_after", "reference_type", "reference_id", "note", "created_by"]


class AdjustSerializer(serializers.Serializer):
    bucket = serializers.PrimaryKeyRelatedField(queryset=StockBucket.objects.all())
    movement_type = serializers.ChoiceField(choices=["adjustment", "wastage", "expiry", "damage"])
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=3)
    reason = serializers.CharField()


class TransferSerializer(serializers.Serializer):
    bucket = serializers.PrimaryKeyRelatedField(queryset=StockBucket.objects.all())
    to_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class StockTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTransfer
        fields = ["id", "created_at", "from_bucket", "to_bucket", "quantity", "note", "created_by"]

from rest_framework import serializers

from apps.catalog.models import Package
from apps.inventory.models import RawMaterial
from apps.locations.models import Location

from .models import BatchConsumption, PackagingRun, ProductionBatch, Recipe, RecipeLine


class RecipeLineSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = RecipeLine
        fields = ["id", "raw_material", "raw_material_name", "quantity", "unit", "unit_code"]


class RecipeSerializer(serializers.ModelSerializer):
    lines = RecipeLineSerializer(many=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Recipe
        fields = ["id", "product", "product_name", "name", "output_quantity", "is_active", "lines"]

    def create(self, validated):
        lines = validated.pop("lines", [])
        recipe = Recipe.objects.create(**validated)
        for ln in lines:
            RecipeLine.objects.create(recipe=recipe, **ln)
        return recipe

    def update(self, instance, validated):
        lines = validated.pop("lines", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for ln in lines:
                RecipeLine.objects.create(recipe=instance, **ln)
        return instance


class BatchConsumptionSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)

    class Meta:
        model = BatchConsumption
        fields = ["raw_material", "raw_material_name", "quantity"]


class ProductionBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    consumptions = BatchConsumptionSerializer(many=True, read_only=True)

    class Meta:
        model = ProductionBatch
        fields = ["id", "batch_number", "location", "location_name", "product", "product_name", "recipe", "produced_at", "quantity_produced", "expiry_date", "notes", "quality_passed", "quality_notes", "consumptions"]
        read_only_fields = ["batch_number", "product", "produced_at", "expiry_date", "consumptions"]


class BatchCreateSerializer(serializers.Serializer):
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    quantity_produced = serializers.DecimalField(max_digits=12, decimal_places=3)
    produced_at = serializers.DateTimeField(required=False)
    expiry_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    quality_passed = serializers.BooleanField(required=False, default=True)
    quality_notes = serializers.CharField(required=False, allow_blank=True, default="")


class PackagingMaterialSerializer(serializers.Serializer):
    raw_material = serializers.PrimaryKeyRelatedField(queryset=RawMaterial.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)


class PackagingCreateSerializer(serializers.Serializer):
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all())
    units = serializers.IntegerField(min_value=1)
    materials = PackagingMaterialSerializer(many=True, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class PackagingRunSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.__str__", read_only=True)

    class Meta:
        model = PackagingRun
        fields = ["id", "batch", "package", "package_name", "units", "bulk_used", "created_at", "notes"]

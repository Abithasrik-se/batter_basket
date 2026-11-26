from rest_framework import serializers

from .models import Package, Price, Product, Unit


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "code", "name", "name_ta", "kind", "factor"]


class ProductSerializer(serializers.ModelSerializer):
    base_unit_code = serializers.CharField(source="base_unit.code", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "name_ta", "product_type", "description", "base_unit", "base_unit_code", "density_kg_per_litre", "hsn_code", "gst_rate", "image", "is_active"]


class PackageSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = Package
        fields = ["id", "product", "product_name", "name", "size", "unit", "unit_code", "is_active"]


class PriceSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.__str__", read_only=True)

    class Meta:
        model = Price
        fields = ["id", "package", "package_name", "price_group", "amount", "effective_from", "effective_to", "is_active"]

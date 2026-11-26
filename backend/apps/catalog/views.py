from rest_framework import viewsets

from apps.accounts.api import AuditedMixin, RBACViewSetMixin

from .models import Package, Price, Product, Unit
from .serializers import PackageSerializer, PriceSerializer, ProductSerializer, UnitSerializer


class CatalogViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    perm_read = "catalog.view"
    perm_write = "catalog.manage"
    location_field = None


class UnitViewSet(CatalogViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer


class ProductViewSet(CatalogViewSet):
    queryset = Product.objects.select_related("base_unit")
    serializer_class = ProductSerializer
    search_fields = ["name", "name_ta"]
    filterset_fields = ["product_type", "is_active"]


class PackageViewSet(CatalogViewSet):
    queryset = Package.objects.select_related("product", "unit")
    serializer_class = PackageSerializer
    search_fields = ["name", "product__name"]
    filterset_fields = ["product", "is_active"]


class PriceViewSet(CatalogViewSet):
    queryset = Price.objects.select_related("package", "package__product")
    serializer_class = PriceSerializer
    filterset_fields = ["package", "price_group", "is_active"]

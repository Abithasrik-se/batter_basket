from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import AuditedMixin, RBACViewSetMixin

from . import services
from .models import ProductionBatch, Recipe
from .serializers import (BatchCreateSerializer, PackagingCreateSerializer, PackagingRunSerializer,
                          ProductionBatchSerializer, RecipeSerializer)


class RecipeViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Recipe.objects.select_related("product").prefetch_related("lines__raw_material", "lines__unit")
    serializer_class = RecipeSerializer
    perm_read = "production.view"
    perm_write = "catalog.manage"
    location_field = None
    filterset_fields = ["product", "is_active"]
    action_perms = {"requirements": "production.view"}

    @action(detail=True, methods=["get"])
    def requirements(self, request, pk=None):
        """What a batch of ?quantity litres needs, and whether ?location has enough stock."""
        from decimal import Decimal

        from apps.inventory.models import StockBucket
        from apps.locations.models import Location

        from apps.core.money import q3

        from .services import required_materials

        recipe = self.get_object()
        qty = Decimal(request.query_params.get("quantity") or recipe.output_quantity)
        loc = Location.objects.filter(pk=request.query_params.get("location")).first()
        out = []
        for material, need in required_materials(recipe, qty):
            have = None
            if loc:
                from django.db.models import Sum

                have = StockBucket.objects.filter(location=loc, kind="raw", raw_material=material).aggregate(t=Sum("quantity"))["t"] or Decimal("0")
            out.append({"material": material.name, "unit": material.unit.code, "needed": str(need), "in_stock": None if have is None else str(have), "short": None if have is None else str(q3(max(Decimal("0"), need - have)))})
        return Response({"quantity": str(qty), "lines": out})


class ProductionBatchViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    """Batches are created through the service (consumes raw material, adds bulk stock). Not editable."""

    queryset = ProductionBatch.objects.select_related("location", "product").prefetch_related("consumptions__raw_material")
    serializer_class = ProductionBatchSerializer
    perm_read = "production.view"
    perm_write = "production.create"
    action_perms = {"package": "packaging.create"}
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["location", "product", "quality_passed"]
    search_fields = ["batch_number"]

    def create(self, request, *args, **kwargs):
        ser = BatchCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["location"])
        batch = services.create_batch(user=request.user, **d)
        return Response(ProductionBatchSerializer(batch).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        """Only notes can change after production; quantities are history (use stock adjustments for corrections)."""
        batch = self.get_object()
        allowed = {k: v for k, v in request.data.items() if k in ("notes", "quality_notes")}
        ser = self.get_serializer(batch, data=allowed, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        from apps.core import audit

        audit.record(request.user, "production.notes", batch, after=allowed)
        return Response(ser.data)

    @action(detail=True, methods=["post"])
    def package(self, request, pk=None):
        batch = self.get_object()
        ser = PackagingCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        run = services.package_batch(user=request.user, batch=batch, package=d["package"], units=d["units"], materials=d.get("materials"), notes=d.get("notes", ""))
        return Response(PackagingRunSerializer(run).data, status=201)

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import AuditedMixin, RBACViewSetMixin
from apps.accounts.rbac import user_has_perm
from rest_framework.exceptions import PermissionDenied

from . import services
from .models import RawMaterial, StockBucket, StockMovement, StockTransfer
from .serializers import (AdjustSerializer, RawMaterialSerializer, StockBucketSerializer, StockMovementSerializer,
                          StockTransferSerializer, TransferSerializer)


class RawMaterialViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = RawMaterial.objects.select_related("unit")
    serializer_class = RawMaterialSerializer
    perm_read = "inventory.view"
    perm_write = "inventory.create"
    location_field = None
    search_fields = ["name", "name_ta"]
    filterset_fields = ["is_packaging", "is_active"]


class StockBucketViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Current stock. Adjust / transfer are actions so each is permission checked and audited."""

    queryset = StockBucket.objects.select_related("location", "raw_material", "raw_material__unit", "product", "product__base_unit", "package", "package__product", "batch")
    serializer_class = StockBucketSerializer
    perm_read = "inventory.view"
    action_perms = {"adjust": "inventory.adjust", "transfer": "inventory.transfer"}
    filterset_fields = ["location", "kind"]
    search_fields = ["raw_material__name", "product__name", "package__name", "batch__batch_number"]

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        ser = AdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bucket = ser.validated_data["bucket"]
        self.assert_location_access(bucket.location)
        mv = services.adjust_stock(bucket, ser.validated_data["quantity_delta"], ser.validated_data["movement_type"], user=request.user, reason=ser.validated_data["reason"])
        return Response(StockMovementSerializer(mv).data, status=201)

    @action(detail=False, methods=["post"])
    def transfer(self, request):
        ser = TransferSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bucket = ser.validated_data["bucket"]
        self.assert_location_access(bucket.location)
        # the receiving site must also be a site the user may work with
        if not user_has_perm(request.user, "inventory.view", ser.validated_data["to_location"]):
            raise PermissionDenied("You have no access to the destination location.")
        t = services.transfer_stock(bucket, ser.validated_data["to_location"], ser.validated_data["quantity"], user=request.user, note=ser.validated_data["note"])
        return Response(StockTransferSerializer(t).data, status=201)


class StockMovementViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("bucket", "bucket__location", "bucket__raw_material", "bucket__product", "bucket__package")
    serializer_class = StockMovementSerializer
    perm_read = "inventory.view"
    location_field = "bucket__location"
    filterset_fields = ["movement_type", "bucket", "bucket__location", "reference_type", "reference_id"]

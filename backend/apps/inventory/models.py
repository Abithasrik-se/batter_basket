from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class RawMaterial(BaseModel):
    name = models.CharField(max_length=100)
    name_ta = models.CharField(max_length=100, blank=True)
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="+")
    min_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0, help_text="Reorder alert level (per location)")
    is_packaging = models.BooleanField(default=False, help_text="Carry bags, pouches, labels...")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockBucket(BaseModel):
    """Current balance of ONE stock item at ONE location (and batch).

    kind = raw    -> raw_material, measured in raw_material.unit
           bulk   -> product + batch, measured in product.base_unit
           packed -> package + batch, measured in packets (pieces)
    The balance is only ever changed by inventory.services (which also writes the ledger row).
    """

    KINDS = [("raw", "Raw material"), ("bulk", "Bulk batter"), ("packed", "Packaged")]

    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="stock_buckets")
    kind = models.CharField(max_length=10, choices=KINDS)
    raw_material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name="buckets")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="buckets")
    package = models.ForeignKey("catalog.Package", null=True, blank=True, on_delete=models.PROTECT, related_name="buckets")
    batch = models.ForeignKey("production.ProductionBatch", null=True, blank=True, on_delete=models.PROTECT, related_name="buckets")
    key = models.CharField(max_length=120)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reserved = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["location", "key"], name="uniq_bucket_per_location"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="bucket_qty_non_negative"),
            models.CheckConstraint(condition=models.Q(reserved__gte=0), name="bucket_reserved_non_negative"),
            models.CheckConstraint(condition=models.Q(reserved__lte=models.F("quantity")), name="bucket_reserved_le_qty"),
        ]
        indexes = [models.Index(fields=["location", "kind"])]

    @property
    def available(self):
        return self.quantity - self.reserved

    @property
    def item_name(self):
        if self.kind == "raw":
            return self.raw_material.name
        if self.kind == "bulk":
            return f"{self.product.name} (bulk)"
        return str(self.package)

    @property
    def unit_code(self):
        if self.kind == "raw":
            return self.raw_material.unit.code
        if self.kind == "bulk":
            return self.product.base_unit.code
        return "pcs"


class StockMovement(AppendOnlyModel):
    """The inventory ledger. Append-only; balance = sum of deltas."""

    TYPES = [
        ("purchase", "Purchase"), ("production", "Production"), ("consumption", "Consumption"),
        ("packaging", "Packaging"), ("sale", "Sale"), ("return", "Return"),
        ("transfer_out", "Transfer out"), ("transfer_in", "Transfer in"),
        ("adjustment", "Adjustment"), ("wastage", "Wastage"), ("expiry", "Expiry"), ("damage", "Damage"),
    ]

    bucket = models.ForeignKey(StockBucket, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=TYPES, db_index=True)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=~models.Q(quantity_delta=0), name="movement_non_zero")]
        indexes = [models.Index(fields=["reference_type", "reference_id"])]


class StockTransfer(BaseModel):
    from_bucket = models.ForeignKey(StockBucket, on_delete=models.PROTECT, related_name="+")
    to_bucket = models.ForeignKey(StockBucket, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

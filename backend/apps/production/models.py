from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class Recipe(BaseModel):
    """Ingredients needed to make `output_quantity` (in the product's base unit)."""

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="recipes")
    name = models.CharField(max_length=100)
    output_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__name", "name"]

    def __str__(self):
        return self.name


class RecipeLine(BaseModel):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="lines")
    raw_material = models.ForeignKey("inventory.RawMaterial", on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="+", help_text="Unit this quantity is written in (converted to the material's own unit)")


class ProductionBatch(BaseModel):
    batch_number = models.CharField(max_length=40, unique=True)
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="batches")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="batches")
    recipe = models.ForeignKey(Recipe, null=True, on_delete=models.SET_NULL, related_name="batches")
    produced_at = models.DateTimeField()
    quantity_produced = models.DecimalField(max_digits=12, decimal_places=3)
    expiry_date = models.DateField()
    produced_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)
    quality_passed = models.BooleanField(default=True)
    quality_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-produced_at"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity_produced__gt=0), name="batch_qty_positive")]

    def __str__(self):
        return self.batch_number


class BatchConsumption(AppendOnlyModel):
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name="consumptions")
    raw_material = models.ForeignKey("inventory.RawMaterial", on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, help_text="In the raw material's own unit")


class PackagingRun(AppendOnlyModel):
    batch = models.ForeignKey(ProductionBatch, on_delete=models.PROTECT, related_name="packaging_runs")
    package = models.ForeignKey("catalog.Package", on_delete=models.PROTECT, related_name="+")
    units = models.PositiveIntegerField()
    bulk_used = models.DecimalField(max_digits=12, decimal_places=3, help_text="In the product's base unit")
    packed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

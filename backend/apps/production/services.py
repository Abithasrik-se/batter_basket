from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import convert
from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings, next_number
from apps.core.money import q3
from apps.inventory import services as stock

from .models import BatchConsumption, PackagingRun, ProductionBatch


def required_materials(recipe, quantity_produced):
    """[(raw_material, qty_in_material_unit)] needed to produce `quantity_produced`."""
    scale = Decimal(quantity_produced) / recipe.output_quantity
    out = []
    for line in recipe.lines.select_related("raw_material", "raw_material__unit", "unit"):
        qty = convert(line.quantity * scale, line.unit, line.raw_material.unit)
        out.append((line.raw_material, q3(qty)))
    return out


@transaction.atomic
def create_batch(*, user, location, recipe, quantity_produced, produced_at=None, expiry_date=None, notes="", quality_passed=True, quality_notes="") -> ProductionBatch:
    quantity_produced = q3(quantity_produced)
    if quantity_produced <= 0:
        raise BusinessRuleError("Quantity produced must be positive.")
    if not recipe.is_active:
        raise BusinessRuleError("This recipe is inactive.")
    produced_at = produced_at or timezone.now()
    day = timezone.localtime(produced_at).date()
    expiry_date = expiry_date or day + timedelta(days=SystemSettings.load().default_shelf_life_days)
    seq = next_number(f"batch-{location.code}-{day:%Y%m%d}")
    batch = ProductionBatch.objects.create(
        batch_number=f"B-{location.code}-{day:%Y%m%d}-{seq:02d}", location=location, product=recipe.product, recipe=recipe,
        produced_at=produced_at, quantity_produced=quantity_produced, expiry_date=expiry_date, produced_by=user,
        notes=notes, quality_passed=quality_passed, quality_notes=quality_notes,
    )
    for material, qty in required_materials(recipe, quantity_produced):
        bucket = stock.get_bucket(location, "raw", raw_material=material)
        stock.post_movement(bucket, -qty, "consumption", user=user, reference_type="batch", reference_id=batch.id, note=f"Batch {batch.batch_number}")
        BatchConsumption.objects.create(batch=batch, raw_material=material, quantity=qty)
    bulk = stock.get_bucket(location, "bulk", product=recipe.product, batch=batch, expiry_date=expiry_date)
    stock.post_movement(bulk, quantity_produced, "production", user=user, reference_type="batch", reference_id=batch.id)
    audit.record(user, "production.create", batch, after={"batch": batch.batch_number, "qty": str(quantity_produced)})
    return batch


@transaction.atomic
def package_batch(*, user, batch, package, units, materials=None, notes="") -> PackagingRun:
    """Turn bulk batter into packets. Bulk goes down, packets go up, so nothing is counted twice."""
    if package.product_id != batch.product_id:
        raise BusinessRuleError("This package does not belong to the batch's product.")
    if not batch.quality_passed:
        raise BusinessRuleError("This batch failed quality checks and cannot be packaged.")
    if units <= 0:
        raise BusinessRuleError("Units must be positive.")
    bulk_used = q3(convert(package.size * units, package.unit, batch.product.base_unit, product=batch.product))
    bulk = stock.get_bucket(batch.location, "bulk", product=batch.product, batch=batch, expiry_date=batch.expiry_date)
    run = PackagingRun.objects.create(batch=batch, package=package, units=units, bulk_used=bulk_used, packed_by=user, notes=notes)
    stock.post_movement(bulk, -bulk_used, "packaging", user=user, reference_type="packaging", reference_id=run.id)
    packed = stock.get_bucket(batch.location, "packed", package=package, batch=batch, expiry_date=batch.expiry_date)
    stock.post_movement(packed, units, "packaging", user=user, reference_type="packaging", reference_id=run.id)
    for m in materials or []:
        bucket = stock.get_bucket(batch.location, "raw", raw_material=m["raw_material"])
        stock.post_movement(bucket, -q3(m["quantity"]), "consumption", user=user, reference_type="packaging", reference_id=run.id, note="Packaging material")
    audit.record(user, "packaging.create", run, after={"units": units, "bulk_used": str(bulk_used)}, location=batch.location)
    return run

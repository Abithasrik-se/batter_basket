"""All stock changes go through here.

Rules enforced:
  * every change writes an append-only StockMovement
  * balance can never go negative or below the reserved quantity
  * rows are locked (select_for_update) inside a transaction so two cashiers
    cannot sell the same packet twice
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import BusinessRuleError, InsufficientStock
from apps.core.money import q3

from .models import StockBucket, StockMovement, StockTransfer


def bucket_key(kind, raw_material=None, product=None, package=None, batch=None) -> str:
    ref = {"raw": raw_material, "bulk": product, "packed": package}[kind]
    return f"{kind}:{ref.pk}:{batch.pk if batch else '-'}"


@transaction.atomic
def get_bucket(location, kind, *, raw_material=None, product=None, package=None, batch=None, expiry_date=None) -> StockBucket:
    key = bucket_key(kind, raw_material, product, package, batch)
    bucket, _ = StockBucket.objects.get_or_create(
        location=location,
        key=key,
        defaults=dict(kind=kind, raw_material=raw_material, product=product, package=package, batch=batch, expiry_date=expiry_date),
    )
    return bucket


def _lock(bucket) -> StockBucket:
    return StockBucket.objects.select_for_update().get(pk=bucket.pk)


@transaction.atomic
def post_movement(bucket, delta, movement_type, *, user=None, reference_type="", reference_id="", note="") -> StockMovement:
    delta = q3(delta)
    if delta == 0:
        raise BusinessRuleError("Quantity cannot be zero.")
    bucket = _lock(bucket)
    new_qty = bucket.quantity + delta
    if new_qty < 0 or new_qty < bucket.reserved:
        raise InsufficientStock(f"Insufficient stock of {bucket.item_name}: available {bucket.available}, needed {-delta}.")
    bucket.quantity = new_qty
    bucket.save(update_fields=["quantity", "updated_at"])
    return StockMovement.objects.create(
        bucket=bucket, movement_type=movement_type, quantity_delta=delta, balance_after=new_qty,
        reference_type=reference_type, reference_id=str(reference_id), note=note, created_by=user,
    )


# ---- reservations (orders) ------------------------------------------------
def allocate_packed(location, package, qty, *, today=None):
    """FIFO (earliest expiry first) allocation of packed stock. Skips expired batches.
    Must be called inside a transaction. Returns [(bucket, qty)]."""
    today = today or timezone.localdate()
    need = Decimal(qty)
    buckets = (
        StockBucket.objects.select_for_update()
        .filter(location=location, kind="packed", package=package)
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        .order_by(F("expiry_date").asc(nulls_last=True), "created_at")
    )
    out = []
    for b in buckets:
        free = b.quantity - b.reserved
        if free <= 0:
            continue
        take = min(free, need)
        out.append((b, take))
        need -= take
        if need <= 0:
            break
    if need > 0:
        raise InsufficientStock(f"Not enough {package} in stock (short by {need}).")
    return out


def reserve(bucket, qty):
    bucket = _lock(bucket)
    if bucket.quantity - bucket.reserved < qty:
        raise InsufficientStock(f"Not enough free stock of {bucket.item_name}.")
    bucket.reserved += qty
    bucket.save(update_fields=["reserved", "updated_at"])


def release(bucket, qty):
    bucket = _lock(bucket)
    bucket.reserved = max(Decimal("0"), bucket.reserved - qty)
    bucket.save(update_fields=["reserved", "updated_at"])


@transaction.atomic
def consume_reserved(bucket, qty, movement_type, *, user=None, reference_type="", reference_id="", note=""):
    release(bucket, qty)
    return post_movement(bucket, -qty, movement_type, user=user, reference_type=reference_type, reference_id=reference_id, note=note)


# ---- adjustments / transfers ---------------------------------------------
ADJUST_TYPES = {"adjustment", "wastage", "expiry", "damage"}


@transaction.atomic
def adjust_stock(bucket, delta, movement_type, *, user, reason):
    if movement_type not in ADJUST_TYPES:
        raise BusinessRuleError("Invalid adjustment type.")
    if not reason.strip():
        raise BusinessRuleError("A reason is required for stock adjustments.")
    if movement_type != "adjustment" and delta > 0:
        raise BusinessRuleError("Wastage, expiry and damage must reduce stock.")
    before = {"quantity": str(bucket.quantity)}
    mv = post_movement(bucket, delta, movement_type, user=user, note=reason, reference_type="adjustment")
    audit.record(user, f"stock.{movement_type}", bucket, before=before, after={"quantity": str(mv.balance_after), "delta": str(delta)}, reason=reason, location=bucket.location)
    return mv


@transaction.atomic
def transfer_stock(from_bucket, to_location, qty, *, user, note=""):
    qty = q3(qty)
    if qty <= 0:
        raise BusinessRuleError("Transfer quantity must be positive.")
    if from_bucket.location_id == to_location.id:
        raise BusinessRuleError("Source and destination locations are the same.")
    dest = get_bucket(
        to_location, from_bucket.kind, raw_material=from_bucket.raw_material, product=from_bucket.product,
        package=from_bucket.package, batch=from_bucket.batch, expiry_date=from_bucket.expiry_date,
    )
    t = StockTransfer.objects.create(from_bucket=from_bucket, to_bucket=dest, quantity=qty, note=note, created_by=user)
    post_movement(from_bucket, -qty, "transfer_out", user=user, reference_type="transfer", reference_id=t.id, note=note)
    post_movement(dest, qty, "transfer_in", user=user, reference_type="transfer", reference_id=t.id, note=note)
    audit.record(user, "stock.transfer", t, after={"qty": str(qty), "to": str(to_location)}, location=from_bucket.location)
    return t


def raw_stock_by_location(raw_material, location):
    agg = StockBucket.objects.filter(kind="raw", raw_material=raw_material, location=location).aggregate(t=Sum("quantity"))
    return agg["t"] or Decimal("0")

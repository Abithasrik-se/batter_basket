"""Delivery charge calculation: distance slabs + busy-day surge + free-delivery threshold."""
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.db.models import Q

from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings
from apps.core.money import ZERO, q2

from .models import DeliveryFeeSlab, SurgeRule


def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    lat1, lon1, lat2, lon2 = map(lambda v: radians(float(v)), (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return Decimal(str(2 * 6371.0088 * asin(sqrt(a))))


def road_distance_km(location, address):
    """Estimated road km from the production unit to the address pin; None when either has no pin."""
    if location.latitude is None or location.longitude is None:
        return None
    lat, lng = address.latitude, address.longitude
    if lat is None or lng is None:
        lat, lng = address.customer.latitude, address.customer.longitude
    if lat is None or lng is None:
        return None
    factor = SystemSettings.load().road_distance_factor
    return (haversine_km(location.latitude, location.longitude, lat, lng) * factor).quantize(Decimal("0.1"))


def quote(location, address, order_total, date, *, exclude_order=None) -> dict:
    cfg = SystemSettings.load()
    order_total = Decimal(order_total or 0)
    distance = road_distance_km(location, address)
    notes = []
    slab = None

    if distance is None:
        base = q2(cfg.default_delivery_fee)
        notes.append("distance_unknown")
    else:
        if cfg.max_delivery_km and distance > cfg.max_delivery_km:
            raise BusinessRuleError(f"This address is about {distance} km away. We deliver up to {cfg.max_delivery_km} km.")
        slab = (
            DeliveryFeeSlab.objects.filter(location=location, is_active=True, min_km__lte=distance)
            .filter(Q(max_km__isnull=True) | Q(max_km__gte=distance))
            .order_by("-min_km").first()
        )
        if slab:
            base = q2(slab.base_fee + slab.per_km_fee * max(Decimal("0"), distance - slab.min_km))
        else:
            base = q2(cfg.default_delivery_fee)
            notes.append("no_slab")

    from apps.orders.models import Order  # local import: orders depends on delivery.fees

    day_count = Order.objects.filter(location=location, scheduled_date=date).exclude(status="cancelled")
    if exclude_order is not None:
        day_count = day_count.exclude(pk=exclude_order.pk)
    nth = day_count.count() + 1
    surge_rule = SurgeRule.objects.filter(location=location, is_active=True, min_orders__lte=nth).order_by("-min_orders").first()
    surge = ZERO
    if surge_rule:
        surge = q2(base * surge_rule.value / 100) if surge_rule.surcharge_type == "percent" else q2(surge_rule.value)

    total = q2(base + surge)
    free = bool(cfg.free_delivery_above and order_total >= cfg.free_delivery_above)
    if free:
        total = ZERO
        notes.append("free_delivery")
    return {
        "distance_km": str(distance) if distance is not None else None, "slab": slab.label or f"{slab.min_km}-{slab.max_km or '+'} km" if slab else None,
        "base_fee": str(base), "surge_amount": str(surge), "surge_rule": (surge_rule.label or f"{surge_rule.min_orders}+ orders") if surge_rule else None,
        "orders_that_day": nth, "free_delivery_above": str(cfg.free_delivery_above), "total": str(total), "notes": notes,
    }

from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings

from .models import Coupon, CouponRedemption, LoyaltyEntry, Promotion


def free_units(package, quantity, on_date) -> int:
    """How many free packets a line earns from active promotions."""
    best = 0
    for promo in Promotion.objects.filter(is_active=True):
        if promo.package_id not in (None, package.id) or not promo.applies_on(on_date):
            continue
        group = promo.buy_quantity + promo.free_quantity
        best = max(best, (quantity // group) * promo.free_quantity)
    return best


def validate_coupon(code, customer, subtotal, on_date) -> Coupon:
    try:
        coupon = Coupon.objects.get(code__iexact=code, is_active=True)
    except Coupon.DoesNotExist:
        raise BusinessRuleError("Invalid coupon code.")
    if coupon.valid_from > on_date or (coupon.valid_to and coupon.valid_to < on_date):
        raise BusinessRuleError("This coupon is not valid today.")
    if subtotal < coupon.min_order_total:
        raise BusinessRuleError(f"Minimum order for this coupon is {coupon.min_order_total}.")
    if coupon.max_uses is not None and coupon.redemptions.count() >= coupon.max_uses:
        raise BusinessRuleError("This coupon has reached its usage limit.")
    if coupon.redemptions.filter(customer=customer).count() >= coupon.per_customer_limit:
        raise BusinessRuleError("You have already used this coupon.")
    return coupon


def redeem_coupon(coupon, customer, order):
    try:
        with transaction.atomic():
            return CouponRedemption.objects.create(coupon=coupon, customer=customer, order=order)
    except IntegrityError:
        raise BusinessRuleError("Coupon already applied to this order.")


@transaction.atomic
def award_loyalty_for_order(order) -> int:
    """Points = floor(total / 100) * rate. Safe to call twice (unique constraint)."""
    rate = SystemSettings.load().loyalty_points_per_100
    points = int(order.total // Decimal("100")) * rate
    if points <= 0:
        return 0
    try:
        with transaction.atomic():
            LoyaltyEntry.objects.create(customer=order.customer, points=points, reason="order", order=order)
    except IntegrityError:
        return 0
    from apps.customers.models import Customer

    Customer.objects.filter(pk=order.customer_id).update(loyalty_points=order.customer.loyalty_points + points)
    return points

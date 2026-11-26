"""Order lifecycle:  pending -> confirmed -> dispatched -> completed   (cancel allowed before dispatch)

  create   prices the order (history-safe snapshot), applies discounts + GST
  confirm  reserves packed stock FIFO by expiry
  dispatch converts reservations into SALE ledger movements and issues the invoice
  complete marks delivered, awards loyalty points
  cancel   releases reservations (blocked if money was already taken)
  return   after dispatch: records returned packets, optional restock, credit on the invoice
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import get_price
from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings, next_number
from apps.core.money import HUNDRED, ZERO, line_tax, q2
from apps.inventory import services as stock
from apps.promotions import services as promos

from .models import Order, OrderAllocation, OrderLine, OrderReturn, OrderReturnLine, OrderStatusHistory


def _history(order, from_status, to_status, user, note=""):
    OrderStatusHistory.objects.create(order=order, from_status=from_status, to_status=to_status, note=note, changed_by=user)


def _notify(order, event):
    from apps.notifications.services import notify_customer

    notify_customer(order.customer, event, f"Order {order.order_number}", f"Your order {order.order_number} is {order.get_status_display().lower()}. Total: {order.total}")


def _locked(order) -> Order:
    return Order.objects.select_for_update().get(pk=order.pk)


def _price_lines(customer, lines, coupon_pct, today):
    """Price every line (history-safe snapshot). Returns (rows, totals)."""
    cfg = SystemSettings.load()
    tax_applies = cfg.gst_scheme == "regular"
    rows = []
    gross = disc = taxable = tax = payable = ZERO
    for l in lines:
        pkg, qty = l["package"], l["quantity"]
        if not pkg.is_active or not pkg.product.is_active:
            raise BusinessRuleError(f"{pkg} is not available.")
        if qty <= 0:
            raise BusinessRuleError("Quantity must be positive.")
        unit_price = get_price(pkg, customer.price_group, today)
        free = promos.free_units(pkg, qty, today)
        line_gross = q2(unit_price * qty)
        after_promo = line_gross - q2(unit_price * free)
        after_customer = after_promo - q2(after_promo * customer.discount_percent / HUNDRED)
        net = after_customer - q2(after_customer * coupon_pct / HUNDRED)
        tv, tx, total = line_tax(net, pkg.product.gst_rate, inclusive=cfg.prices_include_tax, applicable=tax_applies)
        rows.append(dict(
            package=pkg, quantity=qty, free_quantity=free, unit_price=unit_price, discount_amount=q2(line_gross - net),
            tax_rate=pkg.product.gst_rate if tax_applies else 0, hsn_code=pkg.product.hsn_code,
            taxable_amount=tv, tax_amount=tx, line_total=total,
        ))
        gross += line_gross
        disc += q2(line_gross - net)
        taxable += tv
        tax += tx
        payable += total
    return rows, dict(gross=q2(gross), discount=q2(disc), taxable=q2(taxable), tax=q2(tax), payable=q2(payable))


def order_subtotal(customer, lines):
    """What the items would cost (used for free-delivery thresholds and fee quotes)."""
    _, totals = _price_lines(customer, lines, Decimal("0"), timezone.localdate())
    return totals["payable"]


def _apply_delivery(order, address, payable):
    from apps.delivery import fees

    q = fees.quote(order.location, address, payable, order.scheduled_date, exclude_order=order)
    order.delivery_fee = q2(q["total"])
    order.delivery_distance_km = Decimal(q["distance_km"]) if q["distance_km"] is not None else None
    order.delivery_fee_detail = q


def _write_lines(order, rows, totals, address):
    order.lines.all().delete()
    for r in rows:
        OrderLine.objects.create(order=order, **r)
    order.gross_total, order.discount_total, order.taxable_total, order.tax_total = totals["gross"], totals["discount"], totals["taxable"], totals["tax"]
    _apply_delivery(order, address, totals["payable"])
    order.total = q2(totals["payable"] + order.delivery_fee)


@transaction.atomic
def create_order(*, user, customer, location, lines, delivery_address, source="admin", delivery_instructions="", coupon_code="", scheduled_date=None, **_ignored) -> Order:
    """The delivery address is mandatory; the delivery fee is always calculated by the system (distance + surge)."""
    if not lines:
        raise BusinessRuleError("An order needs at least one line.")
    if not customer.is_active:
        raise BusinessRuleError("This customer is inactive.")
    if delivery_address is None:
        raise BusinessRuleError("A delivery address is required for every order.")
    if delivery_address.customer_id != customer.id:
        raise BusinessRuleError("The delivery address belongs to another customer.")
    today = timezone.localdate()
    scheduled_date = scheduled_date or today

    coupon, coupon_pct = None, Decimal("0")
    if coupon_code:
        gross_for_coupon = sum(get_price(l["package"], customer.price_group, today) * l["quantity"] for l in lines)
        coupon = promos.validate_coupon(coupon_code, customer, gross_for_coupon, today)
        coupon_pct = coupon.discount_percent

    day = timezone.localdate()
    order = Order.objects.create(
        order_number=f"ORD-{day:%Y%m%d}-{next_number(f'order-{day:%Y%m%d}'):04d}", customer=customer, location=location, source=source,
        delivery_address=delivery_address, delivery_instructions=delivery_instructions, scheduled_date=scheduled_date,
        coupon_code=coupon.code if coupon else "", created_by=user,
    )
    rows, totals = _price_lines(customer, lines, coupon_pct, today)
    _write_lines(order, rows, totals, delivery_address)
    order.save()
    if coupon:
        promos.redeem_coupon(coupon, customer, order)
    _history(order, "", "pending", user, "Order created")
    audit.record(user, "order.create", order, after={"total": str(order.total), "source": source, "delivery_fee": str(order.delivery_fee)})
    return order


@transaction.atomic
def update_order(order, user, *, lines=None, delivery_address=None, scheduled_date=None, delivery_instructions=None) -> Order:
    """Pending orders: items, address and date can change (everything is re-priced). Confirmed: instructions only."""
    order = _locked(order)
    if order.status not in ("pending", "confirmed"):
        raise BusinessRuleError("Only pending or confirmed orders can be edited.")
    before = {"total": str(order.total), "address": str(order.delivery_address_id), "date": str(order.scheduled_date)}
    if delivery_instructions is not None:
        order.delivery_instructions = delivery_instructions
    if order.status == "confirmed":
        if lines is not None or delivery_address is not None or scheduled_date is not None:
            raise BusinessRuleError("Items, address and date are locked once an order is confirmed. Cancel it and create a new one.")
        order.save(update_fields=["delivery_instructions", "updated_at"])
        return order
    if delivery_address is not None:
        if delivery_address.customer_id != order.customer_id:
            raise BusinessRuleError("The delivery address belongs to another customer.")
        order.delivery_address = delivery_address
    if scheduled_date is not None:
        order.scheduled_date = scheduled_date
    if lines is not None:
        if not lines:
            raise BusinessRuleError("An order needs at least one line.")
        pct = Decimal("0")
        if order.coupon_code:
            from apps.promotions.models import Coupon

            pct = Coupon.objects.get(code=order.coupon_code).discount_percent
        rows, totals = _price_lines(order.customer, lines, pct, timezone.localdate())
        _write_lines(order, rows, totals, order.delivery_address)
    else:  # address / date changed: item prices stay as they were, only the delivery fee is re-worked
        payable = sum((l.line_total for l in order.lines.all()), ZERO)
        _apply_delivery(order, order.delivery_address, payable)
        order.total = q2(payable + order.delivery_fee)
    order.save()
    audit.record(user, "order.update", order, before=before, after={"total": str(order.total), "address": str(order.delivery_address_id), "date": str(order.scheduled_date)})
    return order


@transaction.atomic
def confirm_order(order, user) -> Order:
    order = _locked(order)
    if order.status != "pending":
        raise BusinessRuleError(f"Only pending orders can be confirmed (this one is {order.status}).")
    for line in order.lines.select_related("package"):
        for bucket, qty in stock.allocate_packed(order.location, line.package, line.quantity):
            stock.reserve(bucket, qty)
            OrderAllocation.objects.create(line=line, bucket=bucket, quantity=qty)
    order.status = "confirmed"
    order.save(update_fields=["status", "updated_at"])
    _history(order, "pending", "confirmed", user)
    _notify(order, "order_confirmed")
    return order


@transaction.atomic
def dispatch_order(order, user) -> Order:
    from apps.billing.services import issue_invoice

    order = _locked(order)
    if order.status != "confirmed":
        raise BusinessRuleError("Only confirmed orders can be dispatched.")
    for alloc in OrderAllocation.objects.select_for_update().filter(line__order=order, status="reserved"):
        stock.consume_reserved(alloc.bucket, alloc.quantity, "sale", user=user, reference_type="order", reference_id=order.id)
        alloc.status = "consumed"
        alloc.save(update_fields=["status", "updated_at"])
    order.status = "dispatched"
    order.save(update_fields=["status", "updated_at"])
    issue_invoice(order, user)
    _history(order, "confirmed", "dispatched", user)
    _notify(order, "order_dispatched")
    return order


@transaction.atomic
def complete_order(order, user, note="") -> Order:
    order = _locked(order)
    if order.status != "dispatched":
        raise BusinessRuleError("Only dispatched orders can be completed.")
    order.status = "completed"
    order.save(update_fields=["status", "updated_at"])
    _history(order, "dispatched", "completed", user, note)
    promos.award_loyalty_for_order(order)
    return order


@transaction.atomic
def cancel_order(order, user, reason) -> Order:
    order = _locked(order)
    if not reason.strip():
        raise BusinessRuleError("A cancellation reason is required.")
    if order.status not in ("pending", "confirmed"):
        raise BusinessRuleError("Dispatched orders cannot be cancelled. Record a return instead.")
    previous = order.status
    for alloc in OrderAllocation.objects.select_for_update().filter(line__order=order, status="reserved"):
        stock.release(alloc.bucket, alloc.quantity)
        alloc.status = "released"
        alloc.save(update_fields=["status", "updated_at"])
    order.status = "cancelled"
    order.save(update_fields=["status", "updated_at"])
    _history(order, previous, "cancelled", user, reason)
    audit.record(user, "order.cancel", order, reason=reason)
    return order


@transaction.atomic
def return_items(order, user, *, items, reason, restock=False) -> OrderReturn:
    """items = [(order_line, quantity)]. Restock only when the packets are still sellable."""
    from apps.billing.services import apply_credit

    order = _locked(order)
    if order.status not in ("dispatched", "completed"):
        raise BusinessRuleError("Only dispatched or completed orders can have returns.")
    if not reason.strip():
        raise BusinessRuleError("A return reason is required.")
    ret = OrderReturn.objects.create(order=order, reason=reason, restocked=restock, created_by=user)
    credit = ZERO
    for line, qty in items:
        if line.order_id != order.id:
            raise BusinessRuleError("Line does not belong to this order.")
        line = OrderLine.objects.select_for_update().get(pk=line.pk)
        if qty <= 0 or qty > line.quantity - line.returned_quantity:
            raise BusinessRuleError("Return quantity exceeds what was delivered.")
        OrderReturnLine.objects.create(order_return=ret, line=line, quantity=qty)
        line.returned_quantity += qty
        line.save(update_fields=["returned_quantity", "updated_at"])
        credit += q2(line.line_total * qty / line.quantity)
        if restock:
            left = Decimal(qty)
            for alloc in OrderAllocation.objects.filter(line=line, status="consumed").order_by("created_at"):
                give = min(left, alloc.quantity)
                stock.post_movement(alloc.bucket, give, "return", user=user, reference_type="order_return", reference_id=ret.id)
                left -= give
                if left <= 0:
                    break
    ret.credit_value = q2(credit)
    # AppendOnly rows allow one save on creation only, so credit is applied via the invoice instead
    OrderReturn.objects.filter(pk=ret.pk).update(credit_value=ret.credit_value)
    apply_credit(order, ret.credit_value, user)
    audit.record(user, "order.return", order, after={"credit": str(ret.credit_value), "restocked": restock}, reason=reason)
    return ret

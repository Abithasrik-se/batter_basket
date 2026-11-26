from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings, next_number
from apps.core.money import ZERO, q2

from .models import CashClosing, Invoice, Payment, Refund


def financial_year(d) -> str:
    """Indian FY runs April-March, e.g. 26-27."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


@transaction.atomic
def issue_invoice(order, user) -> Invoice:
    if hasattr(order, "invoice"):
        return order.invoice
    cfg = SystemSettings.load()
    now = timezone.now()
    fy = financial_year(timezone.localdate())
    seq = next_number(f"invoice-{fy}")
    regular = cfg.gst_scheme == "regular"
    cgst = q2(order.tax_total / 2) if regular else ZERO
    sgst = q2(order.tax_total - cgst) if regular else ZERO
    inv = Invoice.objects.create(
        order=order, invoice_number=f"{cfg.invoice_prefix}/{fy}/{seq:05d}", invoice_type="tax_invoice" if regular else "bill_of_supply",
        customer=order.customer, location=order.location, issued_at=now, business_name=cfg.business_name, business_gstin=cfg.gstin,
        business_address=cfg.business_address, customer_gstin=order.customer.gstin, gross_total=order.gross_total,
        discount_total=order.discount_total, taxable_total=order.taxable_total, cgst=cgst, sgst=sgst, delivery_fee=order.delivery_fee, total=order.total,
    )
    audit.record(user, "invoice.issue", inv, after={"number": inv.invoice_number, "total": str(inv.total)})
    return inv


def paid_amount(invoice) -> Decimal:
    paid = invoice.payments.aggregate(t=Sum("amount"))["t"] or ZERO
    refunded = Refund.objects.filter(payment__invoice=invoice).aggregate(t=Sum("amount"))["t"] or ZERO
    return q2(paid - refunded)


def invoice_outstanding(invoice) -> Decimal:
    return q2(invoice.total - invoice.credit_total - paid_amount(invoice))


def customer_outstanding(customer) -> Decimal:
    return q2(sum((max(invoice_outstanding(i), ZERO) for i in Invoice.objects.filter(customer=customer)), ZERO))


def _sync_order_payment_status(invoice):
    outstanding = invoice_outstanding(invoice)
    paid = paid_amount(invoice)
    if outstanding <= 0 and (paid > 0 or invoice.total - invoice.credit_total <= 0):
        status = "paid"
    elif paid > 0:
        status = "partial"
    else:
        status = "unpaid"
    order = invoice.order
    order.payment_status = status
    order.save(update_fields=["payment_status", "updated_at"])


@transaction.atomic
def apply_credit(order, amount, user):
    inv = Invoice.objects.select_for_update().get(order=order)
    inv.credit_total = q2(inv.credit_total + amount)
    inv.save(update_fields=["credit_total", "updated_at"])
    _sync_order_payment_status(inv)


@transaction.atomic
def record_payment(invoice, *, method, amount, user, tender=None, reference="") -> Payment:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    amount = q2(amount)
    if amount <= 0:
        raise BusinessRuleError("Payment amount must be positive.")
    outstanding = invoice_outstanding(invoice)
    if amount > outstanding:
        raise BusinessRuleError(f"Payment {amount} is more than the outstanding balance {outstanding}.")
    change = None
    if method == "cash" and tender is not None:
        tender = q2(tender)
        if tender < amount:
            raise BusinessRuleError("The cash handed over is less than the amount being paid.")
        change = q2(tender - amount)
    elif method != "cash":
        tender = None
        if method in ("upi", "bank", "gateway") and not reference.strip():
            raise BusinessRuleError("A transaction reference is required for non-cash payments.")
    payment = Payment.objects.create(invoice=invoice, method=method, amount=amount, tender_amount=tender, change_returned=change, reference=reference, received_by=user, received_at=timezone.now())
    _sync_order_payment_status(invoice)
    audit.record(user, "payment.record", payment, after={"amount": str(amount), "method": method}, location=invoice.location)
    return payment


@transaction.atomic
def refund_payment(payment, *, amount, reason, user) -> Refund:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    amount = q2(amount)
    if not reason.strip():
        raise BusinessRuleError("A refund reason is required.")
    already = payment.refunds.aggregate(t=Sum("amount"))["t"] or ZERO
    if amount <= 0 or amount > payment.amount - already:
        raise BusinessRuleError(f"Refund must be between 0.01 and {payment.amount - already}.")
    refund = Refund.objects.create(payment=payment, amount=amount, reason=reason, refunded_by=user, refunded_at=timezone.now())
    _sync_order_payment_status(payment.invoice)
    audit.record(user, "payment.refund", refund, after={"amount": str(amount)}, reason=reason, location=payment.invoice.location)
    return refund


def expected_cash(location, date) -> Decimal:
    cash_in = Payment.objects.filter(invoice__location=location, method="cash", received_at__date=date).aggregate(t=Sum("amount"))["t"] or ZERO
    cash_out = Refund.objects.filter(payment__invoice__location=location, payment__method="cash", refunded_at__date=date).aggregate(t=Sum("amount"))["t"] or ZERO
    return q2(cash_in - cash_out)


@transaction.atomic
def close_cash(location, date, counted, user, notes="") -> CashClosing:
    if CashClosing.objects.filter(location=location, date=date).exists():
        raise BusinessRuleError("Cash is already closed for this day.")
    expected = expected_cash(location, date)
    counted = q2(counted)
    closing = CashClosing.objects.create(location=location, date=date, expected_cash=expected, counted_cash=counted, difference=q2(counted - expected), closed_by=user, notes=notes)
    audit.record(user, "cash.close", closing, after={"expected": str(expected), "counted": str(counted)}, location=location)
    return closing

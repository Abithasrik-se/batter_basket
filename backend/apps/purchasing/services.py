from django.db import transaction

from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.core.money import q2
from apps.inventory import services as stock

from .models import Purchase, PurchaseLine, SupplierPayment


@transaction.atomic
def create_purchase(*, user, supplier, location, purchase_date, lines, invoice_number="") -> Purchase:
    if not lines:
        raise BusinessRuleError("A purchase needs at least one line.")
    purchase = Purchase.objects.create(supplier=supplier, location=location, purchase_date=purchase_date, invoice_number=invoice_number, created_by=user)
    total = 0
    for ln in lines:
        line_total = q2(ln["quantity"] * ln["unit_cost"])
        PurchaseLine.objects.create(purchase=purchase, raw_material=ln["raw_material"], quantity=ln["quantity"], unit_cost=ln["unit_cost"], line_total=line_total)
        total += line_total
    purchase.total = q2(total)
    purchase.save(update_fields=["total", "updated_at"])
    audit.record(user, "purchase.create", purchase, after={"total": str(purchase.total)})
    return purchase


@transaction.atomic
def receive_purchase(purchase: Purchase, user) -> Purchase:
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status == "received":
        raise BusinessRuleError("This purchase was already received (stock is not added twice).")
    for line in purchase.lines.select_related("raw_material"):
        bucket = stock.get_bucket(purchase.location, "raw", raw_material=line.raw_material)
        stock.post_movement(bucket, line.quantity, "purchase", user=user, reference_type="purchase", reference_id=purchase.id)
    purchase.status = "received"
    purchase.save(update_fields=["status", "updated_at"])
    audit.record(user, "purchase.receive", purchase)
    return purchase


@transaction.atomic
def pay_supplier(purchase: Purchase, *, amount, method, paid_on, reference, user) -> SupplierPayment:
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    amount = q2(amount)
    if amount <= 0 or amount > purchase.balance:
        raise BusinessRuleError(f"Payment must be between 0.01 and the balance {purchase.balance}.")
    pay = SupplierPayment.objects.create(purchase=purchase, amount=amount, method=method, paid_on=paid_on, reference=reference, created_by=user)
    audit.record(user, "supplier.payment", pay, after={"amount": str(amount)}, location=purchase.location)
    return pay


@transaction.atomic
def update_purchase(purchase, user, *, supplier=None, location=None, purchase_date=None, invoice_number=None, lines=None) -> Purchase:
    """Draft purchases can be changed freely. Once received, stock has moved, so they are locked."""
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != "draft":
        raise BusinessRuleError("A received purchase cannot be edited (stock was already added).")
    for name, value in (("supplier", supplier), ("location", location), ("purchase_date", purchase_date), ("invoice_number", invoice_number)):
        if value is not None:
            setattr(purchase, name, value)
    if lines is not None:
        if not lines:
            raise BusinessRuleError("A purchase needs at least one line.")
        purchase.lines.all().delete()
        total = 0
        for ln in lines:
            lt = q2(ln["quantity"] * ln["unit_cost"])
            PurchaseLine.objects.create(purchase=purchase, raw_material=ln["raw_material"], quantity=ln["quantity"], unit_cost=ln["unit_cost"], line_total=lt)
            total += lt
        purchase.total = q2(total)
    purchase.save()
    audit.record(user, "purchase.update", purchase, after={"total": str(purchase.total)})
    return purchase


@transaction.atomic
def delete_purchase(purchase, user):
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != "draft":
        raise BusinessRuleError("A received purchase cannot be deleted.")
    audit.record(user, "purchase.delete", purchase, before={"total": str(purchase.total), "invoice": purchase.invoice_number})
    purchase.delete()

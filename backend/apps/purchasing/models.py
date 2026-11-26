from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from apps.core.models import AppendOnlyModel, BaseModel


class Supplier(BaseModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purchase(BaseModel):
    """Supplier invoice. Stock is added to the ledger only when it is *received*."""

    STATUS = [("draft", "Draft"), ("received", "Received")]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="purchases")
    invoice_number = models.CharField(max_length=60, blank=True)
    purchase_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS, default="draft")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-purchase_date", "-created_at"]

    @property
    def paid_amount(self):
        return self.payments.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    @property
    def balance(self):
        return self.total - self.paid_amount

    @property
    def payment_status(self):
        paid = self.paid_amount
        if paid <= 0:
            return "unpaid"
        return "paid" if paid >= self.total else "partial"


class PurchaseLine(BaseModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    raw_material = models.ForeignKey("inventory.RawMaterial", on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_line_qty_positive")]


class SupplierPayment(AppendOnlyModel):
    METHODS = [("cash", "Cash"), ("upi", "UPI"), ("bank", "Bank transfer")]

    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default="cash")
    paid_on = models.DateField()
    reference = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

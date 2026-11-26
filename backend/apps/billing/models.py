from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class Invoice(BaseModel):
    """Issued when an order is dispatched. Business and customer details are snapshotted."""

    TYPES = [("tax_invoice", "Tax Invoice"), ("bill_of_supply", "Bill of Supply")]

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="invoice")
    invoice_number = models.CharField(max_length=40, unique=True)
    invoice_type = models.CharField(max_length=15, choices=TYPES)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="invoices")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="invoices")
    issued_at = models.DateTimeField()
    business_name = models.CharField(max_length=150)
    business_gstin = models.CharField(max_length=15, blank=True)
    business_address = models.TextField(blank=True)
    customer_gstin = models.CharField(max_length=15, blank=True)
    gross_total = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_total = models.DecimalField(max_digits=12, decimal_places=2)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    credit_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Credit from returns")

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["location", "issued_at"])]


class Payment(AppendOnlyModel):
    """Money received against an invoice. Never edited or deleted (refunds are separate rows)."""

    METHODS = [("cash", "Cash"), ("upi", "UPI"), ("bank", "Bank transfer"), ("gateway", "Online gateway")]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=10, choices=METHODS)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount applied to the bill")
    tender_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Cash handed over by the customer")
    change_returned = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=80, blank=True, help_text="UPI / bank reference")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField()

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_positive")]


class Refund(AppendOnlyModel):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    refunded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    refunded_at = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="refund_positive")]


class CashClosing(BaseModel):
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="cash_closings")
    date = models.DateField()
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2)
    counted_cash = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=12, decimal_places=2)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["location", "date"], name="one_cash_closing_per_day")]

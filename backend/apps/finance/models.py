from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Expense(BaseModel):
    CATEGORIES = [
        ("packaging", "Packaging"), ("fuel", "Fuel"), ("vehicle", "Vehicle maintenance"), ("electricity", "Electricity"),
        ("rent", "Rent"), ("delivery", "Delivery"), ("raw_material", "Raw material (cash purchase)"), ("other", "Other"),
    ]

    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="expenses")
    category = models.CharField(max_length=15, choices=CATEGORIES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    paid_via = models.CharField(max_length=10, choices=[("cash", "Cash"), ("upi", "UPI"), ("bank", "Bank")], default="cash")
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="expense_positive")]

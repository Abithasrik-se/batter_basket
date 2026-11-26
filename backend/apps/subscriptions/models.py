from django.db import models

from apps.core.models import BaseModel


class Holiday(BaseModel):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=80)


class Subscription(BaseModel):
    PLANS = [("weekly", "Weekly"), ("monthly", "Monthly"), ("annual", "Annual")]
    STATUS = [("active", "Active"), ("paused", "Paused"), ("cancelled", "Cancelled"), ("expired", "Expired")]

    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="subscriptions")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="subscriptions")
    delivery_address = models.ForeignKey("customers.CustomerAddress", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    plan_type = models.CharField(max_length=10, choices=PLANS, default="monthly")
    start_date = models.DateField()
    end_date = models.DateField()
    delivery_weekdays = models.JSONField(default=list, help_text="0=Monday ... 6=Sunday")
    status = models.CharField(max_length=10, choices=STATUS, default="active", db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    PLAN_DAYS = {"weekly": 7, "monthly": 30, "annual": 365}

    class Meta:
        ordering = ["-created_at"]


class SubscriptionLine(BaseModel):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    package = models.ForeignKey("catalog.Package", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField(default=1)


class SubscriptionRun(BaseModel):
    """One row per (subscription, delivery date). The unique constraint is what prevents duplicate orders."""

    STATUS = [("pending", "Pending"), ("created", "Order created"), ("skipped", "Skipped"), ("failed", "Failed")]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="runs")
    scheduled_date = models.DateField()
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-scheduled_date"]
        constraints = [models.UniqueConstraint(fields=["subscription", "scheduled_date"], name="one_run_per_subscription_day")]

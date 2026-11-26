from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class DeliveryAssignment(BaseModel):
    STATUS = [("assigned", "Assigned"), ("delivered", "Delivered"), ("failed", "Failed")]

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="delivery")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="+")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deliveries")
    route_sequence = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS, default="assigned")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["route_sequence", "created_at"]


class DeliveryRecord(AppendOnlyModel):
    """What the delivery employee reported. Never edited: corrections are NEW rows pointing at the old one."""

    OUTCOMES = [("delivered", "Delivered"), ("failed", "Not delivered")]

    assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.PROTECT, related_name="records")
    outcome = models.CharField(max_length=10, choices=OUTCOMES)
    failed_reason = models.CharField(max_length=255, blank=True)
    customer_confirmed = models.BooleanField(default=False)
    proof_note = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="corrections")
    correction_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]


class DutySession(BaseModel):
    """GPS is only collected while the employee has an open session AND consented."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="duty_sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    consent_given = models.BooleanField(default=False)


class LocationPing(AppendOnlyModel):
    session = models.ForeignKey(DutySession, on_delete=models.CASCADE, related_name="pings")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_m = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField()

    class Meta:
        ordering = ["recorded_at"]
        indexes = [models.Index(fields=["session", "recorded_at"])]


class DeliveryFeeSlab(BaseModel):
    """Distance band pricing: fee = base_fee + per_km_fee x (km beyond min_km). Set per location."""

    location = models.ForeignKey("locations.Location", on_delete=models.CASCADE, related_name="fee_slabs")
    label = models.CharField(max_length=60, blank=True)
    min_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Leave empty for 'and beyond'")
    base_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    per_km_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location", "min_km"]
        constraints = [
            models.CheckConstraint(condition=models.Q(max_km__isnull=True) | models.Q(max_km__gt=models.F("min_km")), name="slab_max_gt_min"),
            models.CheckConstraint(condition=models.Q(base_fee__gte=0) & models.Q(per_km_fee__gte=0), name="slab_fees_non_negative"),
        ]


class SurgeRule(BaseModel):
    """Busy-day surcharge: once a day already has `min_orders` orders at this location, new orders pay extra."""

    TYPES = [("percent", "Percent of delivery fee"), ("flat", "Flat amount")]

    location = models.ForeignKey("locations.Location", on_delete=models.CASCADE, related_name="surge_rules")
    label = models.CharField(max_length=60, blank=True)
    min_orders = models.PositiveIntegerField(help_text="Applies when the day has at least this many orders (including this one)")
    surcharge_type = models.CharField(max_length=10, choices=TYPES, default="percent")
    value = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location", "min_orders"]
        constraints = [models.CheckConstraint(condition=models.Q(value__gte=0), name="surge_value_non_negative")]

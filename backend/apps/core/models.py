import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction


class BaseModel(models.Model):
    """UUID primary key + timestamps for every business table.

    UUIDs are not guessable (/orders/5/ -> /orders/6/ enumeration) and are safe
    to generate offline later (e.g. PWA offline queue).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AppendOnlyModel(BaseModel):
    """Rows can be inserted but never changed or deleted (ledgers, audit trails)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError(f"{self.__class__.__name__} is append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(f"{self.__class__.__name__} is append-only and cannot be deleted.")


class SystemSettings(models.Model):
    """Single-row table with business-wide configuration (pk is always 1)."""

    GST_SCHEMES = [
        ("regular", "Regular (tax invoice, GST collected)"),
        ("composition", "Composition (bill of supply, no GST collected)"),
        ("unregistered", "Unregistered (bill of supply)"),
    ]

    business_name = models.CharField(max_length=150, default="Zeal Enterprises")
    business_address = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    gst_scheme = models.CharField(max_length=20, choices=GST_SCHEMES, default="regular")
    prices_include_tax = models.BooleanField(default=True, help_text="Selling prices already contain GST")
    default_language = models.CharField(max_length=5, default="en")
    currency = models.CharField(max_length=3, default="INR")
    timezone_name = models.CharField(max_length=50, default="Asia/Kolkata")
    invoice_prefix = models.CharField(max_length=10, default="ZE")
    default_shelf_life_days = models.PositiveSmallIntegerField(default=2)
    loyalty_points_per_100 = models.PositiveSmallIntegerField(default=1)
    # Invoice extras
    upi_id = models.CharField(max_length=80, blank=True, help_text="Shown as a pay-by-UPI QR code on invoices")
    bank_details = models.TextField(blank=True)
    invoice_footer = models.TextField(blank=True, default="Thank you for your business!")
    # Delivery pricing
    road_distance_factor = models.DecimalField(max_digits=4, decimal_places=2, default=1.30, help_text="Straight-line km x this = estimated road km")
    default_delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Used when the address has no map pin")
    free_delivery_above = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Orders at or above this value get free delivery (0 = off)")
    max_delivery_km = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="Refuse delivery beyond this distance (0 = no limit)")
    # Attendance / payroll rules
    working_days_per_month = models.PositiveSmallIntegerField(default=26)
    full_day_hours = models.DecimalField(max_digits=4, decimal_places=1, default=6)
    half_day_hours = models.DecimalField(max_digits=4, decimal_places=1, default=3)
    theme = models.JSONField(default=dict, blank=True, help_text="Optional brand token overrides")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "system settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DocumentSequence(models.Model):
    """Gap-free counters for order / invoice / batch numbers."""

    key = models.CharField(max_length=100, unique=True)
    last_value = models.PositiveIntegerField(default=0)


@transaction.atomic
def next_number(key: str) -> int:
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(key=key)
    seq.last_value += 1
    seq.save(update_fields=["last_value"])
    return seq.last_value


class AuditLog(AppendOnlyModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60, db_index=True)
    entity_type = models.CharField(max_length=80, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True)
    location = models.ForeignKey("locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

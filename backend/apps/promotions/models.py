from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class Promotion(BaseModel):
    """Automatic 'buy X get Y free' on a package (or on any package when package is null)."""

    name = models.CharField(max_length=100)
    package = models.ForeignKey("catalog.Package", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    buy_quantity = models.PositiveIntegerField(default=5)
    free_quantity = models.PositiveIntegerField(default=1)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def applies_on(self, date):
        return self.is_active and self.valid_from <= date and (self.valid_to is None or self.valid_to >= date)


class Coupon(BaseModel):
    code = models.CharField(max_length=30, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    min_order_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    per_customer_limit = models.PositiveIntegerField(default=1)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class CouponRedemption(AppendOnlyModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="+")
    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="coupon_redemption")  # one coupon use per order


class LoyaltyEntry(AppendOnlyModel):
    """Points ledger. unique(order, reason) stops a double award for the same order."""

    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="loyalty_entries")
    points = models.IntegerField()
    reason = models.CharField(max_length=30)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "reason"], name="uniq_loyalty_per_order_reason", condition=models.Q(order__isnull=False))]

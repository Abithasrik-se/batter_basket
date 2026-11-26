from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, BaseModel


class Order(BaseModel):
    SOURCES = [("admin", "Admin"), ("website", "Website"), ("pwa", "Mobile app"), ("subscription", "Subscription")]
    STATUS = [("pending", "Pending"), ("confirmed", "Confirmed"), ("dispatched", "Dispatched"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    PAYMENT = [("unpaid", "Unpaid"), ("partial", "Partially paid"), ("paid", "Paid")]

    order_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="orders")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="orders")
    source = models.CharField(max_length=15, choices=SOURCES, default="admin")
    status = models.CharField(max_length=12, choices=STATUS, default="pending", db_index=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT, default="unpaid", db_index=True)
    delivery_address = models.ForeignKey("customers.CustomerAddress", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    delivery_instructions = models.TextField(blank=True)
    scheduled_date = models.DateField()
    coupon_code = models.CharField(max_length=30, blank=True)
    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_distance_km = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    delivery_fee_detail = models.JSONField(default=dict, blank=True, help_text="How the delivery fee was worked out")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["location", "status"]), models.Index(fields=["scheduled_date"])]

    def __str__(self):
        return self.order_number


class OrderLine(BaseModel):
    """Prices and tax are COPIED here so later price changes never alter old orders."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    package = models.ForeignKey("catalog.Package", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    free_quantity = models.PositiveIntegerField(default=0, help_text="Free packets from a promotion (included in quantity)")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=8, blank=True)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    returned_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_line_qty_positive")]


class OrderStatusHistory(AppendOnlyModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["created_at"]


class OrderAllocation(BaseModel):
    """Which stock bucket (batch) an order line takes its packets from."""

    STATUS = [("reserved", "Reserved"), ("consumed", "Consumed"), ("released", "Released")]

    line = models.ForeignKey(OrderLine, on_delete=models.CASCADE, related_name="allocations")
    bucket = models.ForeignKey("inventory.StockBucket", on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    status = models.CharField(max_length=10, choices=STATUS, default="reserved")


class OrderReturn(AppendOnlyModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="returns")
    reason = models.CharField(max_length=255)
    restocked = models.BooleanField(default=False)
    credit_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class OrderReturnLine(AppendOnlyModel):
    order_return = models.ForeignKey(OrderReturn, on_delete=models.PROTECT, related_name="lines")
    line = models.ForeignKey(OrderLine, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()

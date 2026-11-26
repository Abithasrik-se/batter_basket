from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Customer(BaseModel):
    CATEGORIES = [("household", "Household"), ("hotel", "Hotel / bulk")]

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    category = models.CharField(max_length=10, choices=CATEGORIES, default="household")
    price_group = models.CharField(max_length=10, choices=[("household", "Household"), ("hotel", "Hotel"), ("bulk", "Bulk")], default="household")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Customer-specific discount on every order")
    gstin = models.CharField(max_length=15, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preferred_location = models.ForeignKey("locations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True)
    notifications_opt_in = models.BooleanField(default=True, help_text="Consent to order / delivery messages")
    marketing_opt_in = models.BooleanField(default=False)
    loyalty_points = models.IntegerField(default=0)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_profile")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerAddress(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, default="Home")
    address_line = models.TextField()
    area = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "label"]

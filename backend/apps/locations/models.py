from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Location(BaseModel):
    """A production centre / stock location. One business, many sites."""

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=10, unique=True, help_text="Short code used in batch numbers, e.g. SVK")
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_locations")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

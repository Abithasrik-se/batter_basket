from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Notification(BaseModel):
    CHANNELS = [("in_app", "In-app"), ("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")]
    STATUS = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("suppressed", "Suppressed (no consent)")]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    customer = models.ForeignKey("customers.Customer", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    location = models.ForeignKey("locations.Location", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    channel = models.CharField(max_length=10, choices=CHANNELS, default="in_app")
    event = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel

from .rbac import ROLE_LABELS


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, blank=True)
    preferred_language = models.CharField(max_length=5, choices=[("en", "English"), ("ta", "தமிழ்")], default="en")

    def __str__(self):
        return self.get_full_name() or self.username


class Membership(BaseModel):
    """User X holds role R at location L."""

    ROLE_CHOICES = list(ROLE_LABELS.items())

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    location = models.ForeignKey("locations.Location", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "location", "role"], name="uniq_membership")]

    def __str__(self):
        return f"{self.user} - {self.role} @ {self.location}"

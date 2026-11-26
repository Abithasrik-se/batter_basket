from rest_framework import serializers

from .models import AuditLog, SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        exclude = ["id"]


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "user", "user_name", "action", "entity_type", "entity_id", "location", "before", "after", "reason"]

from datetime import timedelta

from rest_framework import serializers

from .models import Holiday, Subscription, SubscriptionLine, SubscriptionRun


class SubscriptionLineSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.__str__", read_only=True)

    class Meta:
        model = SubscriptionLine
        fields = ["id", "package", "package_name", "quantity"]


class SubscriptionSerializer(serializers.ModelSerializer):
    lines = SubscriptionLineSerializer(many=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    end_date = serializers.DateField(required=False)

    class Meta:
        model = Subscription
        fields = ["id", "customer", "customer_name", "location", "delivery_address", "plan_type", "start_date", "end_date", "delivery_weekdays", "status", "notes", "lines"]
        read_only_fields = ["status"]

    def validate(self, attrs):
        addr = attrs.get("delivery_address") or (self.instance.delivery_address if self.instance else None)
        cust = attrs.get("customer") or (self.instance.customer if self.instance else None)
        if addr is None:
            raise serializers.ValidationError({"delivery_address": "A delivery address is required."})
        if cust and addr.customer_id != cust.id:
            raise serializers.ValidationError({"delivery_address": "This address belongs to another customer."})
        return attrs

    def update(self, instance, validated):
        lines = validated.pop("lines", None)
        validated.pop("customer", None)  # a subscription cannot move to another customer
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for l in lines:
                SubscriptionLine.objects.create(subscription=instance, **l)
        return instance

    def validate_delivery_weekdays(self, value):
        if not value or any(not isinstance(d, int) or d < 0 or d > 6 for d in value):
            raise serializers.ValidationError("Choose weekdays as numbers 0 (Mon) to 6 (Sun).")
        return sorted(set(value))

    def create(self, validated):
        lines = validated.pop("lines")
        if "end_date" not in validated:
            validated["end_date"] = validated["start_date"] + timedelta(days=Subscription.PLAN_DAYS[validated["plan_type"]])
        sub = Subscription.objects.create(**validated)
        for l in lines:
            SubscriptionLine.objects.create(subscription=sub, **l)
        return sub


class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionRun
        fields = ["id", "subscription", "scheduled_date", "order", "status", "note"]


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name"]

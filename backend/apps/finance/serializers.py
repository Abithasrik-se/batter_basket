from rest_framework import serializers

from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Expense
        fields = ["id", "location", "location_name", "category", "amount", "expense_date", "description", "paid_via", "is_void", "void_reason", "created_by"]
        read_only_fields = ["is_void", "void_reason", "created_by"]

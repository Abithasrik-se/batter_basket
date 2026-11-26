from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import RBACViewSetMixin
from apps.core import audit
from apps.core.exceptions import BusinessRuleError

from .models import Expense
from .serializers import ExpenseSerializer


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ExpenseViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    """Expenses are never deleted: they are voided with a reason (and audited)."""

    queryset = Expense.objects.select_related("location")
    serializer_class = ExpenseSerializer
    perm_read = "expenses.view"
    perm_write = "expenses.create"
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["location", "category", "is_void", "expense_date"]
    search_fields = ["description"]

    def perform_create(self, serializer):
        self.assert_location_access(serializer.validated_data["location"])
        e = serializer.save(created_by=self.request.user)
        audit.record(self.request.user, "expense.create", e, after={"amount": str(e.amount), "category": e.category})

    def perform_update(self, serializer):
        old = serializer.instance
        if old.is_void:
            raise BusinessRuleError("A void expense cannot be edited.")
        before = ExpenseSerializer(old).data
        if serializer.validated_data.get("location"):
            self.assert_location_access(serializer.validated_data["location"])
        e = serializer.save()
        audit.record(self.request.user, "expense.update", e, before=before, after=ExpenseSerializer(e).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        e = self.get_object()
        ser = VoidSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if e.is_void:
            raise BusinessRuleError("Already void.")
        e.is_void, e.void_reason = True, ser.validated_data["reason"]
        e.save(update_fields=["is_void", "void_reason", "updated_at"])
        audit.record(request.user, "expense.void", e, reason=e.void_reason)
        return Response(ExpenseSerializer(e).data)

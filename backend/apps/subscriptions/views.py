from datetime import date

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.api import AuditedMixin, RBACViewSetMixin
from apps.core import audit

from . import services
from .models import Holiday, Subscription, SubscriptionRun
from .serializers import HolidaySerializer, RunSerializer, SubscriptionSerializer


class SubscriptionViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("customer", "location").prefetch_related("lines__package__product")
    serializer_class = SubscriptionSerializer
    perm_read = "orders.view"
    perm_write = "subscriptions.manage"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["status", "location", "customer"]

    def perform_destroy(self, instance):
        """Deleting a subscription cancels it (order history is kept)."""
        services.cancel(instance)
        audit.record(self.request.user, "subscription.cancel", instance)

    def _do(self, request, fn):
        sub = self.get_object()
        fn(sub)
        audit.record(request.user, f"subscription.{fn.__name__}", sub)
        return Response(self.get_serializer(sub).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self._do(request, services.pause)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._do(request, services.resume)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._do(request, services.cancel)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        return self._do(request, services.renew)

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        sub = self.get_object()
        services.skip_delivery(sub, request.data.get("date"))
        return Response({"detail": "Delivery skipped."})

    @action(detail=False, methods=["post"], url_path="generate-orders")
    def generate_orders(self, request):
        """Manual trigger of the daily job (same code Celery runs)."""
        return Response(services.generate_orders_for_date(date.fromisoformat(request.data["date"]) if request.data.get("date") else None))


class SubscriptionRunViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = SubscriptionRun.objects.select_related("subscription")
    serializer_class = RunSerializer
    perm_read = "orders.view"
    location_field = "subscription__location"
    filterset_fields = ["subscription", "status", "scheduled_date"]


class HolidayViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    perm_read = "orders.view"
    perm_write = "subscriptions.manage"
    location_field = None

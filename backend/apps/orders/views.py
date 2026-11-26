from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.api import RBACViewSetMixin

from . import services
from .models import Order, OrderLine
from .serializers import CancelSerializer, OrderCreateSerializer, OrderSerializer, OrderUpdateSerializer, ReturnSerializer


class OrderViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    queryset = Order.objects.select_related("customer", "location").prefetch_related("lines__package__product", "history")
    serializer_class = OrderSerializer
    perm_read = "orders.view"
    perm_write = "orders.create"
    action_perms = {
        "confirm": "orders.confirm", "dispatch_order": "orders.dispatch", "complete": "orders.dispatch",
        "cancel": "orders.cancel", "return_items": "orders.return",
    }
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["status", "payment_status", "location", "customer", "source", "scheduled_date"]
    search_fields = ["order_number", "customer__name", "customer__phone"]

    def create(self, request, *args, **kwargs):
        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["location"])
        order = services.create_order(user=request.user, **d)
        return Response(OrderSerializer(order).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        """Pending: items / address / date / instructions (re-priced). Confirmed: instructions only."""
        order = self.get_object()
        ser = OrderUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        order = services.update_order(order, request.user, **d)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return Response(self.get_serializer(services.confirm_order(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_order(self, request, pk=None):
        # NOTE: the Python method must not be called `dispatch` (that name belongs to Django's View).
        return Response(self.get_serializer(services.dispatch_order(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return Response(self.get_serializer(services.complete_order(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        ser = CancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(self.get_serializer(services.cancel_order(self.get_object(), request.user, ser.validated_data["reason"])).data)

    @action(detail=True, methods=["post"], url_path="return")
    def return_items(self, request, pk=None):
        order = self.get_object()
        ser = ReturnSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = []
        for it in ser.validated_data["items"]:
            try:
                line = OrderLine.objects.get(pk=it["line"], order=order)
                items.append((line, int(it["quantity"])))
            except (OrderLine.DoesNotExist, KeyError, ValueError, TypeError):
                raise ValidationError("Each item needs a valid 'line' and 'quantity'.")
        services.return_items(order, request.user, items=items, reason=ser.validated_data["reason"], restock=ser.validated_data["restock"])
        return Response(self.get_serializer(order).data)

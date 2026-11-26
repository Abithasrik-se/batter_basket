from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from apps.accounts.api import RBACPermission, RBACViewSetMixin
from apps.accounts.rbac import locations_with_perm, user_has_perm
from apps.orders.models import Order

from . import services
from .models import DeliveryAssignment, DeliveryRecord, LocationPing
from .serializers import DeliveryAssignmentSerializer, DeliveryRecordSerializer, LocationPingSerializer


class AssignSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    employee = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())
    route_sequence = serializers.IntegerField(min_value=1, default=1)


class RecordSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["delivered", "failed"])
    failed_reason = serializers.CharField(required=False, allow_blank=True, default="")
    customer_confirmed = serializers.BooleanField(default=False)
    proof_note = serializers.CharField(required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)


class CollectSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["cash", "upi"])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    tender_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True, default="")


class CorrectSerializer(serializers.Serializer):
    record = serializers.PrimaryKeyRelatedField(queryset=DeliveryRecord.objects.all())
    outcome = serializers.ChoiceField(choices=["delivered", "failed"])
    failed_reason = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField()


class DeliveryAssignmentViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Employees see only THEIR deliveries; managers see their locations'."""

    queryset = DeliveryAssignment.objects.select_related("order", "order__customer", "order__delivery_address", "employee").prefetch_related("records")
    serializer_class = DeliveryAssignmentSerializer
    perm_read = "delivery.view"
    action_perms = {"assign": "delivery.assign", "record": "delivery.record", "collect": "delivery.record", "correct": "delivery.correct"}
    filterset_fields = ["status", "employee", "location"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        managed = locations_with_perm(user, "delivery.assign")
        return qs.filter(Q(employee=user) | Q(location__in=managed))

    @action(detail=False, methods=["post"])
    def assign(self, request):
        ser = AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["order"].location)
        a = services.assign_delivery(d["order"], d["employee"], request.user, d["route_sequence"])
        return Response(self.get_serializer(a).data, status=201)

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        a = self.get_object()
        ser = RecordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.record_delivery(a, request.user, **ser.validated_data)
        a.refresh_from_db()
        return Response(self.get_serializer(a).data, status=201)

    @action(detail=True, methods=["post"])
    def collect(self, request, pk=None):
        a = self.get_object()
        ser = CollectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        services.collect_payment(a, request.user, method=d["method"], amount=d["amount"], tender=d.get("tender_amount"), reference=d["reference"])
        a.refresh_from_db()
        return Response(self.get_serializer(a).data, status=201)

    @action(detail=False, methods=["post"])
    def correct(self, request):
        ser = CorrectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        self.assert_location_access(d["record"].assignment.location)
        new = services.correct_record(d["record"], request.user, outcome=d["outcome"], reason=d["reason"], failed_reason=d["failed_reason"])
        return Response(DeliveryRecordSerializer(new).data, status=201)


class DutyView(APIView):
    """POST /delivery/duty/ {"action": "start"|"end"|"ping", ...}. Employees only; GPS needs consent."""

    permission_classes = [RBACPermission]

    def required_permission(self, request):
        return "delivery.record"

    def post(self, request):
        act = request.data.get("action")
        if act == "start":
            s = services.start_duty(request.user, bool(request.data.get("consent")))
            return Response({"session": str(s.id), "started_at": s.started_at}, status=201)
        if act == "end":
            services.end_duty(request.user)
            return Response({"detail": "Duty ended."})
        if act == "ping":
            try:
                lat, lng = float(request.data["latitude"]), float(request.data["longitude"])
            except (KeyError, ValueError, TypeError):
                return Response({"detail": "latitude and longitude are required."}, status=400)
            services.add_ping(request.user, round(lat, 6), round(lng, 6), request.data.get("accuracy"))
            return Response({"detail": "ok"}, status=201)
        return Response({"detail": "Unknown action."}, status=400)


class TrackingView(APIView):
    """GET /delivery/tracking/?user=<id>&date=YYYY-MM-DD  (delivery.track, same location only)."""

    permission_classes = [RBACPermission]

    def required_permission(self, request):
        return "delivery.track"

    def get(self, request):
        target = get_user_model().objects.filter(pk=request.query_params.get("user")).first()
        if not target:
            return Response({"detail": "user is required"}, status=400)
        allowed = request.user.is_superuser or target.memberships.filter(location__in=locations_with_perm(request.user, "delivery.track")).exists()
        if not allowed:
            raise PermissionDenied("This employee works at a location you cannot track.")
        pings = LocationPing.objects.filter(session__user=target, recorded_at__date=request.query_params.get("date"))
        return Response(LocationPingSerializer(pings, many=True).data)


class DeliveryRecordViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryRecord.objects.select_related("assignment")
    serializer_class = DeliveryRecordSerializer
    perm_read = "delivery.assign"
    location_field = "assignment__location"
    filterset_fields = ["assignment", "outcome"]


from apps.accounts.api import AuditedMixin  # noqa: E402
from apps.customers.models import CustomerAddress, Customer  # noqa: E402
from apps.locations.models import Location  # noqa: E402

from . import fees  # noqa: E402
from .models import DeliveryFeeSlab, SurgeRule  # noqa: E402
from .serializers import DeliveryFeeSlabSerializer, SurgeRuleSerializer  # noqa: E402


class DeliveryFeeSlabViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    """Distance based delivery charges. View: delivery.view, change: delivery.fees."""

    queryset = DeliveryFeeSlab.objects.select_related("location")
    serializer_class = DeliveryFeeSlabSerializer
    perm_read = "delivery.view"
    perm_write = "delivery.fees"
    filterset_fields = ["location", "is_active"]


class SurgeRuleViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = SurgeRule.objects.select_related("location")
    serializer_class = SurgeRuleSerializer
    perm_read = "delivery.view"
    perm_write = "delivery.fees"
    filterset_fields = ["location", "is_active"]


class FeeQuoteView(APIView):
    """POST /delivery/quote/ {location, delivery_address, lines?, scheduled_date?}  ->  what the delivery will cost."""

    permission_classes = [RBACPermission]

    def required_permission(self, request):
        return "orders.create"

    def post(self, request):
        from datetime import date as _date

        from django.utils import timezone

        from apps.orders.services import order_subtotal

        loc = Location.objects.filter(pk=request.data.get("location")).first()
        addr = CustomerAddress.objects.select_related("customer").filter(pk=request.data.get("delivery_address")).first()
        if not loc or not addr:
            raise PermissionDenied("location and delivery_address are required.")
        if not user_has_perm(request.user, "orders.create", loc):
            raise PermissionDenied("You do not have access to this location.")
        when = request.data.get("scheduled_date")
        when = _date.fromisoformat(when) if when else timezone.localdate()
        lines = []
        from apps.catalog.models import Package

        for l in request.data.get("lines") or []:
            pkg = Package.objects.select_related("product").filter(pk=l.get("package")).first()
            if pkg and int(l.get("quantity") or 0) > 0:
                lines.append({"package": pkg, "quantity": int(l["quantity"])})
        total = order_subtotal(addr.customer, lines) if lines else 0
        return Response(fees.quote(loc, addr, total, when))

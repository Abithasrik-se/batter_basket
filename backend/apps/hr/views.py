from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api import AuditedMixin, RBACViewSetMixin
from apps.accounts.rbac import locations_with_perm
from apps.core import audit
from apps.core.exceptions import BusinessRuleError

from . import payroll as payroll_service
from .models import Attendance, EmployeeProfile, PayrollEntry
from .serializers import AttendanceSerializer, EmployeeProfileSerializer, PayrollEntrySerializer


class EmployeeProfileViewSet(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    queryset = EmployeeProfile.objects.select_related("user", "location")
    serializer_class = EmployeeProfileSerializer
    perm_read = "employees.view"
    perm_write = "employees.manage"
    filterset_fields = ["location", "is_active", "salary_type"]
    search_fields = ["user__username", "user__first_name", "job_title"]


class AttendanceViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    """Admin view of attendance. Staff check themselves in/out via /attendance/check/.
    Edits and manual entries need a reason and are audited (before/after)."""

    queryset = Attendance.objects.select_related("user", "location")
    serializer_class = AttendanceSerializer
    perm_read = "employees.view"
    perm_write = "employees.manage"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["user", "location", "date"]
    search_fields = ["user__username"]

    def _reason(self, serializer):
        reason = (self.request.data.get("reason") or "").strip()
        if not reason:
            raise ValidationError({"reason": "A reason is required for attendance corrections."})
        return reason

    def perform_create(self, serializer):
        reason = self._reason(serializer)
        self.assert_location_access(serializer.validated_data["location"])
        serializer.validated_data.pop("reason", None)
        att = serializer.save(source="manual", note=serializer.validated_data.get("note") or reason)
        audit.record(self.request.user, "attendance.create", att, reason=reason, after=AttendanceSerializer(att).data)

    def perform_update(self, serializer):
        reason = self._reason(serializer)
        before = AttendanceSerializer(serializer.instance).data
        serializer.validated_data.pop("reason", None)
        att = serializer.save()
        audit.record(self.request.user, "attendance.update", att, reason=reason, before=before, after=AttendanceSerializer(att).data)

    def perform_destroy(self, instance):
        reason = self._reason(None)
        audit.record(self.request.user, "attendance.delete", instance, reason=reason, before=AttendanceSerializer(instance).data)
        instance.delete()


class CheckInOutView(APIView):
    """Self-service for every staff member with an active membership."""

    def _membership(self, user):
        m = user.memberships.filter(is_active=True).select_related("location").first()
        if not m:
            raise BusinessRuleError("You are not assigned to any location.")
        return m

    def get(self, request):
        """Today's status + the last 31 days (so an employee can see what payroll will be based on)."""
        today = timezone.localdate()
        recent = Attendance.objects.filter(user=request.user, date__gte=today - timedelta(days=31)).select_related("location", "user")
        todays = recent.filter(date=today).first()
        return Response({
            "today": AttendanceSerializer(todays).data if todays else None,
            "state": "none" if not todays else ("in" if todays.check_out is None else "out"),
            "recent": AttendanceSerializer(recent, many=True).data,
        })

    def post(self, request):
        user = request.user
        membership = self._membership(user)
        today = timezone.localdate()
        if request.data.get("action") == "out":
            att = Attendance.objects.filter(user=user, date=today, check_out__isnull=True).first()
            if not att:
                raise BusinessRuleError("You have not checked in today.")
            att.check_out = timezone.now()
            att.save(update_fields=["check_out", "updated_at"])
        else:
            att, created = Attendance.objects.get_or_create(user=user, date=today, defaults=dict(location=membership.location, check_in=timezone.now()))
            if not created:
                raise BusinessRuleError("You have already checked in today.")
        return Response(AttendanceSerializer(att).data, status=201)


class MonthSerializer(serializers.Serializer):
    month = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$", required=False)
    location = serializers.UUIDField(required=False)


class PayrollEntryViewSet(RBACViewSetMixin, viewsets.ModelViewSet):
    """Salary data is sensitive: payroll.manage for read AND write. Entries are voided, never deleted."""

    queryset = PayrollEntry.objects.select_related("user", "location")
    serializer_class = PayrollEntrySerializer
    perm_read = "payroll.manage"
    perm_write = "payroll.manage"
    http_method_names = ["get", "post", "head", "options"]
    action_perms = {"preview": "payroll.manage", "generate": "payroll.manage", "void": "payroll.manage"}
    filterset_fields = ["user", "location", "entry_type", "is_void"]

    def perform_create(self, serializer):
        self.assert_location_access(serializer.validated_data["location"])
        entry = serializer.save(created_by=self.request.user)
        audit.record(self.request.user, "payroll.create", entry, after={"type": entry.entry_type, "amount": str(entry.amount)})

    def _month(self, request):
        ser = MonthSerializer(data=request.data if request.method == "POST" else request.query_params)
        ser.is_valid(raise_exception=True)
        month = ser.validated_data.get("month") or timezone.localdate().strftime("%Y-%m")
        locs = self.allowed_locations()
        if ser.validated_data.get("location"):
            locs = locs.filter(pk=ser.validated_data["location"])
        y, m = map(int, month.split("-"))
        return y, m, locs, month

    @action(detail=False, methods=["get"])
    def preview(self, request):
        """What each employee is owed for ?month=YYYY-MM, worked out from attendance."""
        y, m, locs, month = self._month(request)
        return Response({"month": month, "rows": payroll_service.preview(locs, y, m)})

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Create the salary entries for the month (once per employee; void an entry to regenerate)."""
        y, m, locs, month = self._month(request)
        return Response({"month": month, **payroll_service.generate(locs, y, m, request.user)})

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        entry = self.get_object()
        payroll_service.void_entry(entry, request.data.get("reason", ""), request.user)
        return Response(PayrollEntrySerializer(entry).data)

from rest_framework import serializers

from apps.accounts.rbac import user_has_perm

from .models import Attendance, EmployeeProfile, PayrollEntry


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = ["id", "user", "username", "name", "location", "job_title", "joining_date", "is_active", "salary_type", "base_salary", "hourly_rate", "emergency_contact"]

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    SALARY_FIELDS = ("base_salary", "hourly_rate")

    def _can_see_salary(self, location):
        request = self.context.get("request")
        return bool(request and user_has_perm(request.user, "payroll.manage", location))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._can_see_salary(instance.location):
            for f in self.SALARY_FIELDS:
                data.pop(f, None)  # salary is only for people with payroll.manage
        return data

    def validate(self, attrs):
        loc = attrs.get("location") or (self.instance.location if self.instance else None)
        if not self._can_see_salary(loc):
            for f in self.SALARY_FIELDS:
                attrs.pop(f, None)
        return attrs


class AttendanceSerializer(serializers.ModelSerializer):
    hours = serializers.FloatField(read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    reason = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Attendance
        fields = ["id", "user", "user_name", "location", "location_name", "date", "check_in", "check_out", "hours", "source", "note", "reason"]
        read_only_fields = ["source"]

    def validate(self, attrs):
        ci, co = attrs.get("check_in", getattr(self.instance, "check_in", None)), attrs.get("check_out", getattr(self.instance, "check_out", None))
        if ci and co and co <= ci:
            raise serializers.ValidationError("Check-out must be after check-in.")
        return attrs


class PayrollEntrySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PayrollEntry
        fields = ["id", "user", "user_name", "location", "entry_type", "amount", "period", "note", "is_auto", "is_void", "void_reason", "created_by", "created_at"]
        read_only_fields = ["is_auto", "is_void", "void_reason", "created_by", "created_at"]

    def validate_entry_type(self, value):
        if value == "salary":
            raise serializers.ValidationError("Salary entries are generated from attendance (Payroll -> Generate).")
        return value

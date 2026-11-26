from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class EmployeeProfile(BaseModel):
    SALARY_TYPES = [("monthly", "Monthly salary"), ("hourly", "Hourly wage")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="employees")
    job_title = models.CharField(max_length=80)
    joining_date = models.DateField()
    is_active = models.BooleanField(default=True)
    salary_type = models.CharField(max_length=10, choices=SALARY_TYPES, default="monthly")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    emergency_contact = models.CharField(max_length=120, blank=True)


class Attendance(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=[("self", "Self check-in"), ("manual", "Entered by admin")], default="self")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="one_attendance_per_day")]

    @property
    def hours(self):
        if not self.check_out:
            return None
        return round((self.check_out - self.check_in).total_seconds() / 3600, 2)


class PayrollEntry(BaseModel):
    """Money lines for an employee. Never deleted: a wrong entry is voided with a reason (and audited)."""

    TYPES = [("salary", "Salary (from attendance)"), ("advance", "Advance"), ("bonus", "Bonus"), ("deduction", "Deduction")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_entries")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT, related_name="+")
    entry_type = models.CharField(max_length=10, choices=TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.DateField(help_text="Any date in the month this belongs to (salary entries use the 1st)")
    note = models.CharField(max_length=255, blank=True)
    is_auto = models.BooleanField(default=False, help_text="Generated from attendance")
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-period", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payroll_amount_positive"),
            models.UniqueConstraint(fields=["user", "period"], condition=models.Q(is_auto=True, is_void=False, entry_type="salary"), name="one_auto_salary_per_month"),
        ]

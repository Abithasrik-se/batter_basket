"""Payroll from attendance.

Day credit  : hours >= full_day_hours -> 1 day, >= half_day_hours -> 0.5 day, else 0
Monthly pay : base_salary / working_days_per_month x credited days (capped at working days)
Hourly pay  : hourly_rate x hours worked
Net payable : salary pay + bonuses - advances - deductions
Days with a check-in but no check-out (before today) are flagged and earn nothing until an admin fixes them.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.core.models import SystemSettings
from apps.core.money import ZERO, q2

from .models import Attendance, EmployeeProfile, PayrollEntry


def month_start(year, month) -> date:
    return date(year, month, 1)


def credit_for(hours: Decimal, cfg) -> Decimal:
    if hours >= cfg.full_day_hours:
        return Decimal("1")
    if hours >= cfg.half_day_hours:
        return Decimal("0.5")
    return Decimal("0")


def compute(profile: EmployeeProfile, year: int, month: int) -> dict:
    cfg = SystemSettings.load()
    first = month_start(year, month)
    last = date(year, month, calendar.monthrange(year, month)[1])
    today = timezone.localdate()
    days = hours_total = credited = Decimal("0")
    incomplete = []
    for att in Attendance.objects.filter(user=profile.user, date__gte=first, date__lte=last).order_by("date"):
        if att.check_out is None:
            if att.date < today:
                incomplete.append(str(att.date))
            continue
        hrs = Decimal(str(att.hours))
        hours_total += hrs
        days += 1
        credited += credit_for(hrs, cfg)

    if profile.salary_type == "hourly":
        pay = q2(hours_total * profile.hourly_rate)
        basis = f"{q2(hours_total)} h x {profile.hourly_rate}"
    else:
        working = Decimal(cfg.working_days_per_month)
        pay = q2(profile.base_salary / working * min(credited, working))
        basis = f"{profile.base_salary} / {cfg.working_days_per_month} x {credited} days"

    entries = PayrollEntry.objects.filter(user=profile.user, period__year=year, period__month=month, is_void=False)
    total = lambda t: entries.filter(entry_type=t).aggregate(s=Sum("amount"))["s"] or ZERO
    bonus, advance, deduction = total("bonus"), total("advance"), total("deduction")
    existing = entries.filter(entry_type="salary", is_auto=True).first()
    return {
        "user": str(profile.user_id), "employee": profile.user.get_full_name() or profile.user.username, "location": str(profile.location_id),
        "salary_type": profile.salary_type, "days_present": int(days), "credited_days": str(credited), "hours": str(q2(hours_total)),
        "incomplete_days": incomplete, "attendance_pay": str(pay), "basis": basis, "bonus": str(bonus), "advance": str(advance), "deduction": str(deduction),
        "net_payable": str(q2((existing.amount if existing else pay) + bonus - advance - deduction)),
        "salary_entry": str(existing.amount) if existing else None, "already_generated": existing is not None,
    }


def preview(locations, year, month):
    profiles = EmployeeProfile.objects.filter(location__in=locations, is_active=True).select_related("user", "location")
    return [compute(p, year, month) for p in profiles]


@transaction.atomic
def generate(locations, year, month, by_user) -> dict:
    created, skipped = 0, []
    for p in EmployeeProfile.objects.filter(location__in=locations, is_active=True).select_related("user", "location"):
        row = compute(p, year, month)
        if row["already_generated"]:
            skipped.append({"employee": row["employee"], "reason": "already generated"})
            continue
        pay = Decimal(row["attendance_pay"])
        if pay <= 0:
            skipped.append({"employee": row["employee"], "reason": "no attendance pay"})
            continue
        entry = PayrollEntry.objects.create(
            user=p.user, location=p.location, entry_type="salary", amount=pay, period=month_start(year, month), is_auto=True,
            note=f"Attendance: {row['credited_days']} days, {row['hours']} h ({row['basis']})", created_by=by_user,
        )
        audit.record(by_user, "payroll.generate", entry, after={"amount": str(pay), "month": f"{year}-{month:02d}"}, location=p.location)
        created += 1
    return {"created": created, "skipped": skipped}


@transaction.atomic
def void_entry(entry: PayrollEntry, reason: str, user):
    if entry.is_void:
        raise BusinessRuleError("Already void.")
    if not reason.strip():
        raise BusinessRuleError("A reason is required.")
    entry.is_void, entry.void_reason = True, reason
    entry.save(update_fields=["is_void", "void_reason", "updated_at"])
    audit.record(user, "payroll.void", entry, reason=reason, location=entry.location)

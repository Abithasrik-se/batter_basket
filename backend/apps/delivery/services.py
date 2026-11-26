from django.db import transaction
from django.utils import timezone

from apps.accounts.rbac import user_has_perm
from apps.billing import services as billing
from apps.core import audit
from apps.core.exceptions import BusinessRuleError
from apps.orders import services as order_services

from .models import DeliveryAssignment, DeliveryRecord, DutySession, LocationPing


@transaction.atomic
def assign_delivery(order, employee, user, sequence=1) -> DeliveryAssignment:
    if order.status not in ("confirmed", "dispatched"):
        raise BusinessRuleError("Only confirmed or dispatched orders can be assigned for delivery.")
    if not user_has_perm(employee, "delivery.record", order.location):
        raise BusinessRuleError("This employee is not a delivery employee at the order's location.")
    obj, created = DeliveryAssignment.objects.get_or_create(order=order, defaults=dict(location=order.location, employee=employee, route_sequence=sequence, assigned_by=user))
    if not created:
        if obj.status == "delivered":
            raise BusinessRuleError("This order was already delivered.")
        before = {"employee": str(obj.employee_id), "sequence": obj.route_sequence}
        obj.employee, obj.route_sequence, obj.assigned_by, obj.status = employee, sequence, user, "assigned"
        obj.save()
        audit.record(user, "delivery.reassign", obj, before=before, after={"employee": str(employee.id), "sequence": sequence}, location=order.location)
    else:
        audit.record(user, "delivery.assign", obj, after={"employee": str(employee.id)}, location=order.location)
    return obj


def _effective_outcome(assignment):
    last = assignment.records.order_by("-created_at").first()
    return last.outcome if last else None


@transaction.atomic
def record_delivery(assignment, user, *, outcome, failed_reason="", customer_confirmed=False, proof_note="", latitude=None, longitude=None) -> DeliveryRecord:
    assignment = DeliveryAssignment.objects.select_for_update().get(pk=assignment.pk)
    if assignment.employee_id != user.id:
        raise BusinessRuleError("This delivery is assigned to someone else.")
    if assignment.status == "delivered":
        raise BusinessRuleError("This delivery is already recorded as delivered.")
    if outcome == "failed" and not failed_reason.strip():
        raise BusinessRuleError("Please give a reason for the failed delivery.")
    if outcome == "delivered" and assignment.order.status != "dispatched":
        raise BusinessRuleError("The order must be dispatched before it can be delivered.")
    rec = DeliveryRecord.objects.create(assignment=assignment, outcome=outcome, failed_reason=failed_reason, customer_confirmed=customer_confirmed, proof_note=proof_note, latitude=latitude, longitude=longitude, recorded_by=user)
    assignment.status = outcome
    assignment.save(update_fields=["status", "updated_at"])
    if outcome == "delivered":
        order_services.complete_order(assignment.order, user, note="Delivered")
    return rec


@transaction.atomic
def correct_record(record, user, *, outcome, reason, failed_reason="") -> DeliveryRecord:
    """Admin correction. The original row stays untouched; a new row supersedes it and the audit log keeps who/why."""
    if not reason.strip():
        raise BusinessRuleError("A reason is required for corrections.")
    new = DeliveryRecord.objects.create(
        assignment=record.assignment, outcome=outcome, failed_reason=failed_reason, customer_confirmed=record.customer_confirmed,
        proof_note=record.proof_note, latitude=record.latitude, longitude=record.longitude, recorded_by=user, supersedes=record, correction_reason=reason,
    )
    assignment = record.assignment
    assignment.status = outcome
    assignment.save(update_fields=["status", "updated_at"])
    audit.record(user, "delivery.correct", new, before={"outcome": record.outcome, "failed_reason": record.failed_reason}, after={"outcome": outcome, "failed_reason": failed_reason}, reason=reason, location=assignment.location)
    return new


@transaction.atomic
def collect_payment(assignment, user, *, method, amount, tender=None, reference=""):
    if assignment.employee_id != user.id:
        raise BusinessRuleError("This delivery is assigned to someone else.")
    order = assignment.order
    if not hasattr(order, "invoice"):
        raise BusinessRuleError("The order has no invoice yet (dispatch it first).")
    return billing.record_payment(order.invoice, method=method, amount=amount, tender=tender, reference=reference, user=user)


def start_duty(user, consent: bool) -> DutySession:
    if not consent:
        raise BusinessRuleError("Location sharing needs your consent to start a duty session.")
    open_session = DutySession.objects.filter(user=user, ended_at__isnull=True).first()
    if open_session:
        return open_session
    return DutySession.objects.create(user=user, started_at=timezone.now(), consent_given=True)


def end_duty(user):
    n = DutySession.objects.filter(user=user, ended_at__isnull=True).update(ended_at=timezone.now())
    if not n:
        raise BusinessRuleError("No open duty session.")


def add_ping(user, latitude, longitude, accuracy=None) -> LocationPing:
    session = DutySession.objects.filter(user=user, ended_at__isnull=True, consent_given=True).first()
    if not session:
        raise BusinessRuleError("Start a duty session (with consent) before sharing location.")
    return LocationPing.objects.create(session=session, latitude=latitude, longitude=longitude, accuracy_m=accuracy, recorded_at=timezone.now())

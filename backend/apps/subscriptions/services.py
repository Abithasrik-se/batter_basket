from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.orders import services as order_services

from .models import Holiday, Subscription, SubscriptionRun


def generate_orders_for_date(date=None) -> dict:
    """Create one order per due subscription for `date`. Safe to run many times."""
    date = date or timezone.localdate()
    stats = {"created": 0, "skipped": 0, "failed": 0, "already": 0}
    Subscription.objects.filter(status="active", end_date__lt=date).update(status="expired")
    is_holiday = Holiday.objects.filter(date=date).exists()
    subs = Subscription.objects.filter(status="active", start_date__lte=date, end_date__gte=date).select_related("customer", "location").prefetch_related("lines__package__product")
    for sub in subs:
        if date.weekday() not in sub.delivery_weekdays:
            continue
        try:
            with transaction.atomic():
                run = SubscriptionRun.objects.create(subscription=sub, scheduled_date=date)
        except IntegrityError:
            stats["already"] += 1
            continue
        if is_holiday:
            run.status, run.note = "skipped", "Holiday"
            stats["skipped"] += 1
        else:
            try:
                with transaction.atomic():
                    order = order_services.create_order(
                        user=None, customer=sub.customer, location=sub.location, source="subscription", scheduled_date=date,
                        delivery_address=sub.delivery_address, delivery_instructions=f"Subscription {sub.id}",
                        lines=[{"package": l.package, "quantity": l.quantity} for l in sub.lines.all()],
                    )
                run.order, run.status = order, "created"
                stats["created"] += 1
            except BusinessRuleError as exc:
                run.status, run.note = "failed", str(exc.detail)[:250]
                stats["failed"] += 1
        run.save()
    return stats


def pause(sub):
    if sub.status != "active":
        raise BusinessRuleError("Only active subscriptions can be paused.")
    sub.status = "paused"
    sub.save(update_fields=["status", "updated_at"])


def resume(sub):
    if sub.status != "paused":
        raise BusinessRuleError("Only paused subscriptions can be resumed.")
    sub.status = "active"
    sub.save(update_fields=["status", "updated_at"])


def cancel(sub):
    if sub.status in ("cancelled", "expired"):
        raise BusinessRuleError("Subscription is already closed.")
    sub.status = "cancelled"
    sub.save(update_fields=["status", "updated_at"])


def renew(sub, user=None):
    """Extend by one plan period from today (or from the current end date if later)."""
    base = max(sub.end_date, timezone.localdate())
    sub.end_date = base + timedelta(days=Subscription.PLAN_DAYS[sub.plan_type])
    if sub.status in ("expired", "cancelled"):
        sub.status = "active"
    sub.save(update_fields=["end_date", "status", "updated_at"])


def skip_delivery(sub, date, note="Skipped by customer"):
    """Customer skips a single delivery."""
    SubscriptionRun.objects.get_or_create(subscription=sub, scheduled_date=date, defaults=dict(status="skipped", note=note))

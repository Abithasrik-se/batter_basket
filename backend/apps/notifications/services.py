"""Notification hub. Email works today (console backend in dev). SMS / WhatsApp / push are
channel stubs: they record the message as `pending` until a provider is connected."""
from datetime import timedelta

from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone

from .models import Notification


def notify_customer(customer, event, title, body, channel="email"):
    """Respects consent: customers who opted out get a `suppressed` record, nothing is sent."""
    if not customer.notifications_opt_in and event not in ("password_reset",):
        return Notification.objects.create(customer=customer, channel=channel, event=event, title=title, body=body, status="suppressed")
    note = Notification.objects.create(customer=customer, channel=channel, event=event, title=title, body=body)
    if channel == "email" and customer.email:
        try:
            send_mail(title, body, None, [customer.email], fail_silently=False)
            note.status = "sent"
        except Exception:  # never break an order because email failed
            note.status = "failed"
        note.save(update_fields=["status", "updated_at"])
    return note


def notify_staff(location, event, title, body):
    from apps.accounts.models import Membership
    from apps.accounts.rbac import roles_granting

    users = {m.user for m in Membership.objects.filter(location=location, is_active=True, role__in=roles_granting("notifications.view")).select_related("user")}
    today = timezone.localdate()
    created = []
    for u in users:
        if Notification.objects.filter(recipient=u, event=event, title=title, created_at__date=today).exists():
            continue  # one alert per user per day
        created.append(Notification.objects.create(recipient=u, location=location, event=event, title=title, body=body, status="sent"))
    return created


def check_stock_alerts() -> int:
    """Low raw material and packets expiring within a day, per location."""
    from apps.inventory.models import RawMaterial, StockBucket
    from apps.locations.models import Location

    count = 0
    soon = timezone.localdate() + timedelta(days=1)
    for loc in Location.objects.filter(is_active=True):
        for rm in RawMaterial.objects.filter(is_active=True, min_stock__gt=0):
            total = StockBucket.objects.filter(location=loc, kind="raw", raw_material=rm).aggregate(t=Sum("quantity"))["t"] or 0
            if total < rm.min_stock:
                count += len(notify_staff(loc, "low_stock", f"Low stock: {rm.name}", f"{rm.name} at {loc.name}: {total} {rm.unit.code} (minimum {rm.min_stock})."))
        for b in StockBucket.objects.filter(location=loc, kind="packed", quantity__gt=0, expiry_date__lte=soon).select_related("package", "package__product"):
            count += len(notify_staff(loc, "expiry", f"Expiring: {b.package}", f"{b.quantity} packets expire on {b.expiry_date}."))
    return count

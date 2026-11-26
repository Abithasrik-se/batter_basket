from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.delivery.models import LocationPing


class Command(BaseCommand):
    help = "Delete GPS pings older than N days (data retention policy). Default 30."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts["days"])
        # AppendOnlyModel blocks instance.delete(); retention uses a queryset delete on purpose.
        deleted, _ = LocationPing.objects.filter(recorded_at__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted} pings older than {opts['days']} days.")

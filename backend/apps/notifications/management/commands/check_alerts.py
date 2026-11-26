from django.core.management.base import BaseCommand

from apps.notifications.services import check_stock_alerts


class Command(BaseCommand):
    help = "Create low-stock and expiry alerts (also run daily by Celery beat)."

    def handle(self, *args, **opts):
        self.stdout.write(f"{check_stock_alerts()} alerts created.")

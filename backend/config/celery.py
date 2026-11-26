"""Celery app. Workers: `celery -A config worker -l info` (add `--pool=solo` on Windows)."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("zeal")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "generate-subscription-orders-daily": {
        "task": "apps.subscriptions.tasks.generate_subscription_orders",
        "schedule": crontab(hour=4, minute=0),
    },
    "check-stock-alerts-daily": {
        "task": "apps.notifications.tasks.check_stock_alerts",
        "schedule": crontab(hour=6, minute=0),
    },
}

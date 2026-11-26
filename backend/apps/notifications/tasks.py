from celery import shared_task

from .services import check_stock_alerts as _check


@shared_task
def check_stock_alerts():
    return _check()

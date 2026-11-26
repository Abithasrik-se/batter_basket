from celery import shared_task

from .services import generate_orders_for_date


@shared_task
def generate_subscription_orders():
    return generate_orders_for_date()

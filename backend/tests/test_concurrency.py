"""Two cashiers confirming orders for the last packets at the same moment.
Only runs on databases with row locking (PostgreSQL); SQLite is skipped."""
import threading
from decimal import Decimal

from django.db import connection, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.core.exceptions import InsufficientStock
from apps.inventory.models import StockBucket
from apps.orders import services as orders

from .helpers import World
from .test_orders_billing import place


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    def test_last_packets_cannot_be_reserved_twice(self):
        w = World()
        w.stock_raw()
        w.make_packets(units=10)
        a, b = place(w, qty=8), place(w, qty=8)
        results = []

        def run(order):
            try:
                orders.confirm_order(order, w.owner)
                results.append("ok")
            except InsufficientStock:
                results.append("short")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(o,)) for o in (a, b)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), ["ok", "short"])
        packed = StockBucket.objects.get(kind="packed")
        self.assertEqual(packed.reserved, Decimal("8.000"))

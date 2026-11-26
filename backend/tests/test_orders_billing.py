from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import Payment
from apps.catalog.models import Price
from apps.core.exceptions import BusinessRuleError, InsufficientStock
from apps.core.models import AuditLog, SystemSettings
from apps.inventory.models import StockBucket, StockMovement
from apps.orders import services as orders
from apps.production import services as prod
from apps.promotions.models import Coupon, Promotion
from apps.promotions import services as promos

from .helpers import World


def address_for(customer):
    from apps.customers.models import CustomerAddress

    return customer.addresses.first() or CustomerAddress.objects.create(customer=customer, address_line="1 Test Street, Sivakasi", is_default=True)


def place(w, qty=5, customer=None, **kw):
    customer = customer or w.customer
    kw.setdefault("delivery_address", address_for(customer))
    return orders.create_order(user=w.cashier, customer=customer, location=w.loc, lines=[{"package": w.pkg1, "quantity": qty}], **kw)


class OrderLifecycleTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.batch = self.w.make_packets(units=40)

    def test_price_and_gst_snapshot(self):
        order = place(self.w, qty=5)
        line = order.lines.get()
        self.assertEqual(line.unit_price, Decimal("55.00"))
        self.assertEqual(order.total, Decimal("275.00"))  # prices include GST
        self.assertEqual(order.taxable_total, Decimal("261.90"))
        self.assertEqual(order.tax_total, Decimal("13.10"))
        # later price change must not touch the existing order
        Price.objects.filter(package=self.w.pkg1, price_group="household").update(amount=Decimal("99"))
        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("55.00"))

    def test_hotel_price_and_customer_discount(self):
        order = place(self.w, qty=10, customer=self.w.hotel)
        self.assertEqual(order.lines.get().unit_price, Decimal("50.00"))
        self.assertEqual(order.total, Decimal("490.00"))  # 500 - 2%

    def test_composition_scheme_charges_no_gst_and_issues_bill_of_supply(self):
        s = SystemSettings.load(); s.gst_scheme = "composition"; s.save()
        order = place(self.w, qty=2)
        self.assertEqual(order.tax_total, Decimal("0.00"))
        orders.confirm_order(order, self.w.owner)
        orders.dispatch_order(order, self.w.owner)
        self.assertEqual(order.invoice.invoice_type, "bill_of_supply")

    def test_full_lifecycle_updates_stock_ledger(self):
        order = place(self.w, qty=5)
        orders.confirm_order(order, self.w.owner)
        packed = StockBucket.objects.get(kind="packed", batch=self.batch)
        self.assertEqual((packed.quantity, packed.reserved, packed.available), (Decimal("40.000"), Decimal("5.000"), Decimal("35.000")))
        orders.dispatch_order(order, self.w.owner)
        packed.refresh_from_db()
        self.assertEqual((packed.quantity, packed.reserved), (Decimal("35.000"), Decimal("0.000")))
        self.assertTrue(StockMovement.objects.filter(movement_type="sale", reference_id=str(order.id), quantity_delta=Decimal("-5")).exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "dispatched")
        self.assertTrue(order.invoice.invoice_number.startswith("ZE/"))
        orders.complete_order(order, self.w.owner)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")

    def test_cannot_oversell(self):
        big = place(self.w, qty=41)
        with self.assertRaises(InsufficientStock):
            orders.confirm_order(big, self.w.owner)
        big.refresh_from_db()
        self.assertEqual(big.status, "pending")
        a, b = place(self.w, qty=30), place(self.w, qty=30)
        orders.confirm_order(a, self.w.owner)
        with self.assertRaises(InsufficientStock):
            orders.confirm_order(b, self.w.owner)  # only 10 left unreserved

    def test_cancel_releases_reservation_and_needs_reason(self):
        order = place(self.w, qty=5)
        orders.confirm_order(order, self.w.owner)
        with self.assertRaises(BusinessRuleError):
            orders.cancel_order(order, self.w.owner, "")
        orders.cancel_order(order, self.w.owner, "Customer changed mind")
        packed = StockBucket.objects.get(kind="packed", batch=self.batch)
        self.assertEqual(packed.reserved, Decimal("0.000"))
        self.assertEqual(packed.quantity, Decimal("40.000"))

    def test_dispatched_order_cannot_be_cancelled(self):
        order = place(self.w, qty=1)
        orders.confirm_order(order, self.w.owner)
        orders.dispatch_order(order, self.w.owner)
        with self.assertRaises(BusinessRuleError):
            orders.cancel_order(order, self.w.owner, "too late")

    def test_fifo_uses_earliest_expiry_first_and_skips_expired(self):
        from apps.production.models import ProductionBatch

        old = self.batch
        newer = self.w.make_packets(units=10, expiry_date=timezone.localdate() + timedelta(days=5))
        order = place(self.w, qty=45)
        orders.confirm_order(order, self.w.owner)
        allocs = {a.bucket.batch_id: a.quantity for l in order.lines.all() for a in l.allocations.all()}
        self.assertEqual(allocs[old.id], Decimal("40.000"))
        self.assertEqual(allocs[newer.id], Decimal("5.000"))
        # expired batch is never sold
        ProductionBatch.objects.filter(pk=old.pk).update(expiry_date=timezone.localdate() - timedelta(days=1))
        StockBucket.objects.filter(batch=old).update(expiry_date=timezone.localdate() - timedelta(days=1))
        order2 = place(self.w, qty=6)
        with self.assertRaises(InsufficientStock):
            orders.confirm_order(order2, self.w.owner)

    def test_return_with_restock_and_credit(self):
        order = place(self.w, qty=5)
        orders.confirm_order(order, self.w.owner)
        orders.dispatch_order(order, self.w.owner)
        line = order.lines.get()
        orders.return_items(order, self.w.owner, items=[(line, 2)], reason="Sour smell", restock=True)
        packed = StockBucket.objects.get(kind="packed", batch=self.batch)
        self.assertEqual(packed.quantity, Decimal("37.000"))
        order.invoice.refresh_from_db()
        self.assertEqual(order.invoice.credit_total, Decimal("110.00"))
        with self.assertRaises(BusinessRuleError):
            orders.return_items(order, self.w.owner, items=[(line, 4)], reason="x")  # only 3 left to return


class BillingTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.w.make_packets(units=40)
        self.order = place(self.w, qty=5)  # 275.00
        orders.confirm_order(self.order, self.w.owner)
        orders.dispatch_order(self.order, self.w.owner)
        self.inv = self.order.invoice

    def test_cash_with_change_stores_applied_tender_and_change_separately(self):
        p = billing.record_payment(self.inv, method="cash", amount=Decimal("250"), tender=Decimal("500"), user=self.w.cashier)
        self.assertEqual((p.amount, p.tender_amount, p.change_returned), (Decimal("250.00"), Decimal("500.00"), Decimal("250.00")))
        self.assertEqual(billing.invoice_outstanding(self.inv), Decimal("25.00"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "partial")
        billing.record_payment(self.inv, method="upi", amount=Decimal("25"), reference="UPI123", user=self.w.cashier)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")

    def test_payment_validation(self):
        with self.assertRaises(BusinessRuleError):
            billing.record_payment(self.inv, method="cash", amount=Decimal("300"), user=self.w.cashier)  # > outstanding
        with self.assertRaises(BusinessRuleError):
            billing.record_payment(self.inv, method="cash", amount=Decimal("100"), tender=Decimal("50"), user=self.w.cashier)
        with self.assertRaises(BusinessRuleError):
            billing.record_payment(self.inv, method="upi", amount=Decimal("100"), user=self.w.cashier)  # reference missing

    def test_credit_sale_shows_as_outstanding(self):
        self.assertEqual(billing.customer_outstanding(self.w.customer), Decimal("275.00"))
        self.assertEqual(self.order.payment_status, "unpaid")

    def test_refund_rules_and_status(self):
        p = billing.record_payment(self.inv, method="cash", amount=Decimal("275"), user=self.w.cashier)
        with self.assertRaises(BusinessRuleError):
            billing.refund_payment(p, amount=Decimal("10"), reason="", user=self.w.owner)
        billing.refund_payment(p, amount=Decimal("100"), reason="Damaged packets", user=self.w.owner)
        with self.assertRaises(BusinessRuleError):
            billing.refund_payment(p, amount=Decimal("200"), reason="again", user=self.w.owner)  # only 175 refundable
        self.assertEqual(billing.invoice_outstanding(self.inv), Decimal("100.00"))
        self.assertTrue(AuditLog.objects.filter(action="payment.refund").exists())

    def test_payments_are_immutable(self):
        p = billing.record_payment(self.inv, method="cash", amount=Decimal("100"), user=self.w.cashier)
        p.amount = Decimal("1")
        with self.assertRaises(RuntimeError):
            p.save()
        with self.assertRaises(RuntimeError):
            p.delete()

    def test_cash_closing_expected_vs_counted(self):
        billing.record_payment(self.inv, method="cash", amount=Decimal("200"), tender=Decimal("500"), user=self.w.cashier)
        billing.record_payment(self.inv, method="upi", amount=Decimal("75"), reference="U1", user=self.w.cashier)
        today = timezone.localdate()
        self.assertEqual(billing.expected_cash(self.w.loc, today), Decimal("200.00"))  # change returned is NOT cash kept
        c = billing.close_cash(self.w.loc, today, Decimal("195"), self.w.cashier)
        self.assertEqual(c.difference, Decimal("-5.00"))
        with self.assertRaises(BusinessRuleError):
            billing.close_cash(self.w.loc, today, Decimal("195"), self.w.cashier)

    def test_invoice_numbers_are_sequential(self):
        o2 = place(self.w, qty=1)
        orders.confirm_order(o2, self.w.owner)
        orders.dispatch_order(o2, self.w.owner)
        n1, n2 = self.inv.invoice_number, o2.invoice.invoice_number
        self.assertEqual(int(n2.split("/")[-1]), int(n1.split("/")[-1]) + 1)


class PromotionTests(TestCase):
    def setUp(self):
        self.w = World()

    def test_buy_five_get_one_free(self):
        Promotion.objects.create(name="Buy 5 get 1", package=self.w.pkg1, buy_quantity=5, free_quantity=1, valid_from=timezone.localdate() - timedelta(days=1))
        order = place(self.w, qty=12)  # 2 free
        line = order.lines.get()
        self.assertEqual(line.free_quantity, 2)
        self.assertEqual(order.total, Decimal("550.00"))  # 10 x 55

    def test_coupon_single_use_per_customer(self):
        Coupon.objects.create(code="FEST10", discount_percent=Decimal("10"), valid_from=timezone.localdate() - timedelta(days=1), per_customer_limit=1)
        o = place(self.w, qty=2, coupon_code="FEST10")
        self.assertEqual(o.total, Decimal("99.00"))
        with self.assertRaises(BusinessRuleError):
            place(self.w, qty=2, coupon_code="FEST10")
        other = place(self.w, qty=2, customer=self.w.hotel, coupon_code="fest10")  # case-insensitive, different customer
        self.assertEqual(other.coupon_code, "FEST10")

    def test_loyalty_points_awarded_once(self):
        o = place(self.w, qty=10)  # 550 -> 5 points
        self.assertEqual(promos.award_loyalty_for_order(o), 5)
        self.assertEqual(promos.award_loyalty_for_order(o), 0)
        self.w.customer.refresh_from_db()
        self.assertEqual(self.w.customer.loyalty_points, 5)

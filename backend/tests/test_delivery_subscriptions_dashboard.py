from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog
from apps.delivery import services as delivery
from apps.delivery.models import DeliveryRecord, LocationPing
from apps.orders import services as orders
from apps.subscriptions import services as subs
from apps.subscriptions.models import Holiday, Subscription, SubscriptionLine, SubscriptionRun

from .helpers import World, client_for
from .test_orders_billing import place


class DeliveryTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.w.make_packets(units=40)
        self.order = place(self.w, qty=5, delivery_address=self.w.address)
        orders.confirm_order(self.order, self.w.owner)
        orders.dispatch_order(self.order, self.w.owner)
        self.order.refresh_from_db()

    def test_assign_record_and_collect_payment(self):
        a = delivery.assign_delivery(self.order, self.w.rider, self.w.dispatcher, 1)
        delivery.collect_payment(a, self.w.rider, method="cash", amount=Decimal("275"), tender=Decimal("300"))
        delivery.record_delivery(a, self.w.rider, outcome="delivered", customer_confirmed=True)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.payment_status), ("completed", "paid"))

    def test_employee_cannot_record_someone_elses_delivery_or_assign_non_driver(self):
        a = delivery.assign_delivery(self.order, self.w.rider, self.w.dispatcher)
        with self.assertRaises(BusinessRuleError):
            delivery.record_delivery(a, self.w.cashier, outcome="delivered")
        with self.assertRaises(BusinessRuleError):
            delivery.assign_delivery(self.order, self.w.cashier, self.w.dispatcher)

    def test_failed_delivery_needs_reason_and_records_are_append_only(self):
        a = delivery.assign_delivery(self.order, self.w.rider, self.w.dispatcher)
        with self.assertRaises(BusinessRuleError):
            delivery.record_delivery(a, self.w.rider, outcome="failed")
        rec = delivery.record_delivery(a, self.w.rider, outcome="failed", failed_reason="Customer not home")
        rec.failed_reason = "edited"
        with self.assertRaises(RuntimeError):
            rec.save()

    def test_admin_correction_preserves_original_and_audits(self):
        a = delivery.assign_delivery(self.order, self.w.rider, self.w.dispatcher)
        rec = delivery.record_delivery(a, self.w.rider, outcome="failed", failed_reason="No answer")
        new = delivery.correct_record(rec, self.w.owner, outcome="delivered", reason="Customer confirmed by phone")
        self.assertEqual(DeliveryRecord.objects.filter(assignment=a).count(), 2)
        rec.refresh_from_db()
        self.assertEqual(rec.outcome, "failed")  # original untouched
        self.assertEqual(new.supersedes_id, rec.id)
        log = AuditLog.objects.get(action="delivery.correct")
        self.assertEqual((log.before["outcome"], log.after["outcome"], log.reason), ("failed", "delivered", "Customer confirmed by phone"))

    def test_rider_only_sees_own_assignments_through_api(self):
        delivery.assign_delivery(self.order, self.w.rider, self.w.dispatcher)
        self.assertEqual(client_for(self.w.rider).get("/api/v1/delivery/assignments/").json()["count"], 1)
        from apps.accounts.models import Membership, User

        r2 = User.objects.create_user("rider2", password="x-Pass12345")
        Membership.objects.create(user=r2, location=self.w.loc, role="delivery_employee")
        self.assertEqual(client_for(r2).get("/api/v1/delivery/assignments/").json()["count"], 0)
        # and a rider has no access to orders, payments or the dashboard
        for url in ["/api/v1/orders/", "/api/v1/payments/", "/api/v1/dashboard/", "/api/v1/customers/"]:
            self.assertEqual(client_for(self.w.rider).get(url).status_code, 403, url)
        nav = client_for(self.w.rider).get("/api/v1/delivery/assignments/").json()["results"][0]["navigation_url"]
        self.assertIn("google.com/maps", nav)

    def test_gps_needs_consent_and_open_session(self):
        with self.assertRaises(BusinessRuleError):
            delivery.add_ping(self.w.rider, 9.45, 77.8)
        with self.assertRaises(BusinessRuleError):
            delivery.start_duty(self.w.rider, consent=False)
        delivery.start_duty(self.w.rider, consent=True)
        delivery.add_ping(self.w.rider, 9.45, 77.8)
        self.assertEqual(LocationPing.objects.count(), 1)
        delivery.end_duty(self.w.rider)
        with self.assertRaises(BusinessRuleError):
            delivery.add_ping(self.w.rider, 9.45, 77.8)

    def test_tracking_requires_permission_and_shared_location(self):
        delivery.start_duty(self.w.rider, consent=True)
        delivery.add_ping(self.w.rider, 9.45, 77.8)
        today = str(timezone.localdate())
        url = f"/api/v1/delivery/tracking/?user={self.w.rider.id}&date={today}"
        self.assertEqual(client_for(self.w.dispatcher).get(url).status_code, 200)
        self.assertEqual(client_for(self.w.cashier).get(url).status_code, 403)
        self.assertEqual(len(client_for(self.w.owner).get(url).json()), 1)


class SubscriptionTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.w.make_packets(units=40)
        self.today = timezone.localdate()
        self.sub = Subscription.objects.create(
            customer=self.w.customer, location=self.w.loc, delivery_address=self.w.address, plan_type="monthly",
            start_date=self.today - timedelta(days=1), end_date=self.today + timedelta(days=30), delivery_weekdays=list(range(7)),
        )
        SubscriptionLine.objects.create(subscription=self.sub, package=self.w.pkg1, quantity=2)

    def test_generation_is_idempotent(self):
        first = subs.generate_orders_for_date(self.today)
        second = subs.generate_orders_for_date(self.today)
        self.assertEqual((first["created"], second["created"], second["already"]), (1, 0, 1))
        self.assertEqual(SubscriptionRun.objects.filter(subscription=self.sub).count(), 1)
        order = SubscriptionRun.objects.get().order
        self.assertEqual((order.source, order.total), ("subscription", Decimal("110.00")))

    def test_holiday_paused_and_other_weekday_are_not_ordered(self):
        Holiday.objects.create(date=self.today, name="Pongal")
        self.assertEqual(subs.generate_orders_for_date(self.today)["skipped"], 1)
        tomorrow = self.today + timedelta(days=1)
        subs.pause(self.sub)
        self.assertEqual(subs.generate_orders_for_date(tomorrow)["created"], 0)
        subs.resume(self.sub)
        self.sub.delivery_weekdays = [(tomorrow.weekday() + 1) % 7]
        self.sub.save()
        self.assertEqual(subs.generate_orders_for_date(tomorrow)["created"], 0)

    def test_inactive_customer_order_failure_is_recorded_not_raised(self):
        self.w.customer.is_active = False
        self.w.customer.save()
        stats = subs.generate_orders_for_date(self.today)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(SubscriptionRun.objects.get().status, "failed")

    def test_expiry_and_renewal(self):
        future = self.today + timedelta(days=40)
        subs.generate_orders_for_date(future)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "expired")
        subs.renew(self.sub)
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(self.sub.end_date, self.today + timedelta(days=30 + 30) if self.sub.end_date > self.today + timedelta(days=30) else self.today + timedelta(days=30))


class DashboardTests(TestCase):
    def test_dashboard_numbers_come_from_transactions(self):
        from apps.billing import services as billing
        from apps.finance.models import Expense

        w = World()
        w.stock_raw()
        w.make_packets(units=40)
        o = place(w, qty=10)  # 550
        orders.confirm_order(o, w.owner)
        orders.dispatch_order(o, w.owner)
        billing.record_payment(o.invoice, method="cash", amount=Decimal("300"), user=w.cashier)
        Expense.objects.create(location=w.loc, category="fuel", amount=Decimal("100"), expense_date=timezone.localdate())
        d = client_for(w.owner).get("/api/v1/dashboard/").json()
        self.assertEqual(d["sales"]["today"], "550.00")
        self.assertEqual(d["sales"]["cash_collected"], "300.00")
        self.assertEqual(d["finance"]["receivables"], "250.00")
        self.assertEqual(d["production"]["total_batter"], "100.00")
        self.assertEqual(d["stock"]["packaged"][0]["available"], "30.000")
        self.assertEqual(d["top_products"][0]["quantity"], 10)
        self.assertEqual(d["finance"]["expense_breakdown"]["operating"], "100.00")
        self.assertIn("Not an audited", d["finance"]["note"])
        self.assertEqual(client_for(w.owner).get("/api/v1/dashboard/export-sales/").status_code, 200)
        self.assertEqual(client_for(w.prod_mgr).get("/api/v1/dashboard/").status_code, 403)

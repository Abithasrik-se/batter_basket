from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.billing.render import amount_in_words
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog, SystemSettings
from apps.customers.models import Customer, CustomerAddress
from apps.delivery.models import DeliveryFeeSlab, SurgeRule
from apps.hr import payroll
from apps.hr.models import Attendance, EmployeeProfile, PayrollEntry
from apps.inventory.models import StockBucket
from apps.orders import services as orders
from apps.purchasing import services as purch

from .helpers import World, client_for
from .test_orders_billing import address_for, place


class DeliveryFeeTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.w.make_packets(units=40)
        # Seeded demo slabs: 0-3 km 20, 3-8 km 40, 8+ km 60 + 5/km beyond 8. Location pin = Sivakasi.
        self.far = CustomerAddress.objects.create(customer=self.w.customer, address_line="Far village", latitude=Decimal("9.60"), longitude=Decimal("77.80"))
        self.near = CustomerAddress.objects.create(customer=self.w.customer, address_line="Near", latitude=Decimal("9.4600"), longitude=Decimal("77.8100"))

    def quote(self, address, total=100):
        from apps.delivery import fees

        return fees.quote(self.w.loc, address, total, timezone.localdate())

    def test_distance_slab_is_applied(self):
        q = self.quote(self.near)
        self.assertEqual(q["base_fee"], "20.00")
        self.assertLess(Decimal(q["distance_km"]), Decimal("3"))
        q2 = self.quote(self.far)  # ~16 km straight line x 1.3 -> last slab 60 + 5 per km over 8
        self.assertGreater(Decimal(q2["total"]), Decimal("60"))

    def test_unknown_distance_uses_default_fee(self):
        s = SystemSettings.load(); s.default_delivery_fee = Decimal("35"); s.save()
        q = self.quote(address_for(self.w.hotel))
        self.assertEqual((q["total"], q["notes"]), ("35.00", ["distance_unknown"]))

    def test_free_delivery_threshold_and_max_distance(self):
        s = SystemSettings.load(); s.free_delivery_above = Decimal("500"); s.save()
        self.assertEqual(self.quote(self.near, 600)["total"], "0.00")
        self.assertEqual(self.quote(self.near, 100)["total"], "20.00")
        s.max_delivery_km = Decimal("10"); s.save()
        with self.assertRaises(BusinessRuleError):
            self.quote(self.far)

    def test_surge_applies_when_day_is_busy(self):
        SurgeRule.objects.all().delete()
        SurgeRule.objects.create(location=self.w.loc, min_orders=2, surcharge_type="percent", value=50)
        first = place(self.w, qty=1, delivery_address=self.near)
        self.assertEqual(first.delivery_fee, Decimal("20.00"))
        second = place(self.w, qty=1, delivery_address=self.near)  # 2nd order of the day -> +50% of 20
        self.assertEqual(second.delivery_fee, Decimal("30.00"))
        self.assertEqual(second.delivery_fee_detail["surge_amount"], "10.00")
        self.assertEqual(second.total, second.taxable_total + second.tax_total + Decimal("30.00"))

    def test_order_requires_delivery_address(self):
        with self.assertRaises(BusinessRuleError):
            orders.create_order(user=self.w.owner, customer=self.w.customer, location=self.w.loc, lines=[{"package": self.w.pkg1, "quantity": 1}], delivery_address=None)
        r = client_for(self.w.owner).post("/api/v1/orders/", {"customer": str(self.w.customer.id), "location": str(self.w.loc.id), "lines": [{"package": str(self.w.pkg1.id), "quantity": 1}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("delivery_address", r.json())
        other = address_for(self.w.hotel)
        with self.assertRaises(BusinessRuleError):
            place(self.w, delivery_address=other)  # belongs to another customer

    def test_quote_endpoint_and_slab_crud(self):
        c = client_for(self.w.owner)
        r = c.post("/api/v1/delivery/quote/", {"location": str(self.w.loc.id), "delivery_address": str(self.near.id), "lines": [{"package": str(self.w.pkg1.id), "quantity": 2}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["base_fee"], "20.00")
        # overlapping slab is rejected, a clean one is accepted, edit + delete work
        bad = c.post("/api/v1/delivery/fee-slabs/", {"location": str(self.w.loc.id), "min_km": "2", "max_km": "5", "base_fee": "30"}, format="json")
        self.assertEqual(bad.status_code, 400)
        loc2 = self.w.loc2
        ok = c.post("/api/v1/delivery/fee-slabs/", {"location": str(loc2.id), "min_km": "0", "max_km": "5", "base_fee": "25"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        sid = ok.json()["id"]
        self.assertEqual(c.patch(f"/api/v1/delivery/fee-slabs/{sid}/", {"base_fee": "27"}, format="json").status_code, 200)
        self.assertEqual(c.delete(f"/api/v1/delivery/fee-slabs/{sid}/").status_code, 204)
        # only people with delivery.fees may change charges
        self.assertEqual(client_for(self.w.dispatcher).post("/api/v1/delivery/fee-slabs/", {"location": str(self.w.loc.id), "min_km": "30", "base_fee": "1"}, format="json").status_code, 403)
        self.assertEqual(client_for(self.w.dispatcher).get("/api/v1/delivery/fee-slabs/").status_code, 200)


class OrderEditTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()
        self.w.make_packets(units=40)

    def test_pending_order_items_can_be_replaced_and_repriced(self):
        o = place(self.w, qty=2)
        o = orders.update_order(o, self.w.owner, lines=[{"package": self.w.pkg2, "quantity": 1}, {"package": self.w.pkg1, "quantity": 3}])
        self.assertEqual(o.lines.count(), 2)
        self.assertEqual(o.total, Decimal("270.00"))  # 105 + 3x55
        self.assertTrue(AuditLog.objects.filter(action="order.update").exists())

    def test_confirmed_order_only_allows_instructions(self):
        o = place(self.w, qty=2)
        orders.confirm_order(o, self.w.owner)
        orders.update_order(o, self.w.owner, delivery_instructions="Ring twice")
        with self.assertRaises(BusinessRuleError):
            orders.update_order(o, self.w.owner, lines=[{"package": self.w.pkg1, "quantity": 1}])

    def test_edit_via_api(self):
        o = place(self.w, qty=2)
        r = client_for(self.w.owner).patch(f"/api/v1/orders/{o.id}/", {"lines": [{"package": str(self.w.pkg1.id), "quantity": 4}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Decimal(r.json()["total"]), Decimal("220.00"))


class CrudRuleTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()

    def test_delete_of_used_record_is_refused_with_a_clear_message(self):
        self.w.make_packets(units=10)
        r = client_for(self.w.owner).delete(f"/api/v1/products/{self.w.idli.id}/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("inactive", r.json()["detail"])

    def test_unused_master_data_can_be_edited_and_deleted(self):
        c = client_for(self.w.owner)
        r = c.post("/api/v1/suppliers/", {"name": "Temp supplier"}, format="json")
        sid = r.json()["id"]
        self.assertEqual(c.patch(f"/api/v1/suppliers/{sid}/", {"phone": "99999"}, format="json").json()["phone"], "99999")
        self.assertEqual(c.delete(f"/api/v1/suppliers/{sid}/").status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action="supplier.delete").exists())

    def test_draft_purchase_edit_and_delete_but_not_after_receipt(self):
        from apps.inventory.models import RawMaterial
        from apps.purchasing.models import Supplier

        sup = Supplier.objects.create(name="S")
        rice = RawMaterial.objects.get(name="Rice")
        p = purch.create_purchase(user=self.w.owner, supplier=sup, location=self.w.loc, purchase_date=date.today(), lines=[{"raw_material": rice, "quantity": Decimal("5"), "unit_cost": Decimal("10")}])
        c = client_for(self.w.owner)
        r = c.patch(f"/api/v1/purchases/{p.id}/", {"lines": [{"raw_material": str(rice.id), "quantity": "8", "unit_cost": "12"}]}, format="json")
        self.assertEqual((r.status_code, r.json()["total"]), (200, "96.00"))
        purch.receive_purchase(p, self.w.owner)
        self.assertEqual(c.patch(f"/api/v1/purchases/{p.id}/", {"invoice_number": "X"}, format="json").status_code, 400)
        self.assertEqual(c.delete(f"/api/v1/purchases/{p.id}/").status_code, 400)
        draft = purch.create_purchase(user=self.w.owner, supplier=sup, location=self.w.loc, purchase_date=date.today(), lines=[{"raw_material": rice, "quantity": Decimal("1"), "unit_cost": Decimal("1")}])
        self.assertEqual(c.delete(f"/api/v1/purchases/{draft.id}/").status_code, 204)

    def test_recipe_crud_and_requirements_endpoint(self):
        c = client_for(self.w.owner)
        from apps.catalog.models import Unit
        from apps.inventory.models import RawMaterial

        kg = Unit.objects.get(code="kg")
        body = {"product": str(self.w.idli.id), "name": "Light idli", "output_quantity": "50", "lines": [{"raw_material": str(RawMaterial.objects.get(name="Rice").id), "quantity": "18", "unit": str(kg.id)}]}
        r = c.post("/api/v1/recipes/", body, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        rid = r.json()["id"]
        req = c.get(f"/api/v1/recipes/{rid}/requirements/", {"quantity": "100", "location": str(self.w.loc.id)}).json()
        self.assertEqual((req["lines"][0]["needed"], req["lines"][0]["in_stock"], req["lines"][0]["short"]), ("36.000", "500.000", "0.000"))
        req = c.get(f"/api/v1/recipes/{rid}/requirements/", {"quantity": "5000", "location": str(self.w.loc.id)}).json()
        self.assertEqual(req["lines"][0]["short"], "1300.000")  # 1800 kg needed, 500 in stock
        self.assertEqual(c.patch(f"/api/v1/recipes/{rid}/", {"name": "Light idli v2"}, format="json").status_code, 200)

    def test_batch_notes_editable_but_quantity_is_not(self):
        b = self.w.make_batch(10)
        c = client_for(self.w.owner)
        r = c.patch(f"/api/v1/production-batches/{b.id}/", {"notes": "Good set", "quantity_produced": "999"}, format="json")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual((b.notes, b.quantity_produced), ("Good set", Decimal("10.000")))

    def test_customer_created_with_first_address_and_pin(self):
        r = client_for(self.w.owner).post("/api/v1/customers/", {"name": "New", "phone": "9111111111", "address_line": "5 Temple Rd", "address_latitude": "9.4500", "address_longitude": "77.8000"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        addr = r.json()["addresses"][0]
        self.assertEqual((addr["address_line"], addr["latitude"]), ("5 Temple Rd", "9.450000"))

    def test_expense_edit_is_audited(self):
        from apps.finance.models import Expense

        e = Expense.objects.create(location=self.w.loc, category="fuel", amount=Decimal("100"), expense_date=date.today())
        r = client_for(self.w.owner).patch(f"/api/v1/expenses/{e.id}/", {"amount": "120"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        log = AuditLog.objects.get(action="expense.update")
        self.assertEqual((log.before["amount"], log.after["amount"]), ("100.00", "120.00"))

    def test_invoice_print_has_words_hsn_and_qr(self):
        self.w.make_packets(units=10)
        s = SystemSettings.load(); s.upi_id = "zeal@upi"; s.save()
        o = place(self.w, qty=3)
        orders.confirm_order(o, self.w.owner)
        orders.dispatch_order(o, self.w.owner)
        html = client_for(self.w.owner).get(f"/api/v1/invoices/{o.invoice.id}/print/").content.decode()
        self.assertIn("Rupees One Hundred Sixty Five Only", html)
        self.assertIn("2106", html)
        self.assertIn("<svg", html)
        self.assertIn("Scan to pay", html)


class WordsTests(SimpleTestCase):
    def test_amount_in_words(self):
        self.assertEqual(amount_in_words(Decimal("250.00")), "Rupees Two Hundred Fifty Only")
        self.assertEqual(amount_in_words(Decimal("123456.50")), "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only")
        self.assertEqual(amount_in_words(Decimal("0")), "Rupees Zero Only")

    @override_settings(DEBUG=True)
    def test_local_dev_origins_are_trusted(self):
        from django.conf import settings

        self.assertIn("http://127.0.0.1:5173", settings.CSRF_TRUSTED_ORIGINS)
        self.assertIn("http://localhost:5173", settings.CSRF_TRUSTED_ORIGINS)


class AttendancePayrollTests(TestCase):
    def setUp(self):
        self.w = World()
        self.rider = self.w.rider
        self.prof = EmployeeProfile.objects.create(user=self.rider, location=self.w.loc, job_title="Rider", joining_date=date(2025, 1, 1), salary_type="monthly", base_salary=Decimal("13000"))
        self.year, self.month = 2026, 9

    def day(self, d, hours, user=None):
        user = user or self.rider
        tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime(self.year, self.month, d, 9, 0), tz)
        co = ci + timedelta(hours=hours) if hours is not None else None
        Attendance.objects.create(user=user, location=self.w.loc, date=date(self.year, self.month, d), check_in=ci, check_out=co)

    def test_self_check_in_and_out_once_per_day(self):
        c = client_for(self.rider)
        self.assertEqual(c.get("/api/v1/attendance-check/").json()["state"], "none")
        self.assertEqual(c.post("/api/v1/attendance-check/", {"action": "in"}, format="json").status_code, 201)
        self.assertEqual(c.post("/api/v1/attendance-check/", {"action": "in"}, format="json").status_code, 400)
        self.assertEqual(c.get("/api/v1/attendance-check/").json()["state"], "in")
        self.assertEqual(c.post("/api/v1/attendance-check/", {"action": "out"}, format="json").status_code, 201)
        self.assertEqual(c.get("/api/v1/attendance-check/").json()["state"], "out")
        self.assertEqual(c.post("/api/v1/attendance-check/", {"action": "out"}, format="json").status_code, 400)

    def test_monthly_pay_from_full_half_and_short_days(self):
        for d in range(1, 11):
            self.day(d, 8)       # 10 full days
        self.day(11, 4)          # half day
        self.day(12, 2)          # too short: no credit
        row = payroll.compute(self.prof, self.year, self.month)
        self.assertEqual((row["days_present"], row["credited_days"]), (12, "10.5"))
        self.assertEqual(row["attendance_pay"], "5250.00")  # 13000 / 26 x 10.5

    def test_hourly_pay(self):
        self.prof.salary_type, self.prof.hourly_rate = "hourly", Decimal("80")
        self.prof.save()
        self.day(1, 8); self.day(2, 5)
        self.assertEqual(payroll.compute(self.prof, self.year, self.month)["attendance_pay"], "1040.00")

    def test_missing_checkout_is_flagged_and_unpaid(self):
        self.day(1, 8); self.day(2, None)
        row = payroll.compute(self.prof, self.year, self.month)
        self.assertEqual(row["incomplete_days"], ["2026-09-02"])
        self.assertEqual(row["credited_days"], "1")

    def test_generate_once_then_void_and_regenerate_with_advance_and_bonus(self):
        for d in range(1, 27):
            self.day(d, 8)
        PayrollEntry.objects.create(user=self.rider, location=self.w.loc, entry_type="advance", amount=Decimal("2000"), period=date(2026, 9, 10))
        PayrollEntry.objects.create(user=self.rider, location=self.w.loc, entry_type="bonus", amount=Decimal("500"), period=date(2026, 9, 28))
        c = client_for(self.w.owner)
        pv = c.get("/api/v1/payroll/preview/", {"month": "2026-09"}).json()["rows"][0]
        self.assertEqual((pv["attendance_pay"], pv["net_payable"]), ("13000.00", "11500.00"))
        g = c.post("/api/v1/payroll/generate/", {"month": "2026-09"}, format="json").json()
        self.assertEqual(g["created"], 1)
        again = c.post("/api/v1/payroll/generate/", {"month": "2026-09"}, format="json").json()
        self.assertEqual((again["created"], again["skipped"][0]["reason"]), (0, "already generated"))
        entry = PayrollEntry.objects.get(entry_type="salary")
        self.assertEqual(c.post(f"/api/v1/payroll/{entry.id}/void/", {"reason": ""}, format="json").status_code, 400)
        self.assertEqual(c.post(f"/api/v1/payroll/{entry.id}/void/", {"reason": "Wrong days"}, format="json").status_code, 200)
        self.assertEqual(c.post("/api/v1/payroll/generate/", {"month": "2026-09"}, format="json").json()["created"], 1)
        # salary entries cannot be typed in by hand
        r = c.post("/api/v1/payroll/", {"user": str(self.rider.id), "location": str(self.w.loc.id), "entry_type": "salary", "amount": "1", "period": "2026-09-01"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_attendance_correction_needs_reason_and_is_audited(self):
        self.day(3, None)
        att = Attendance.objects.get()
        c = client_for(self.w.owner)
        co = timezone.make_aware(datetime(2026, 9, 3, 17, 0), timezone.get_current_timezone()).isoformat()
        self.assertEqual(c.patch(f"/api/v1/attendance/{att.id}/", {"check_out": co}, format="json").status_code, 400)
        r = c.patch(f"/api/v1/attendance/{att.id}/", {"check_out": co, "reason": "Forgot to check out"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["hours"], 8.0)
        self.assertTrue(AuditLog.objects.filter(action="attendance.update", reason="Forgot to check out").exists())
        # a rider cannot edit attendance or see payroll
        self.assertEqual(client_for(self.rider).patch(f"/api/v1/attendance/{att.id}/", {"reason": "x"}, format="json").status_code, 403)
        self.assertEqual(client_for(self.rider).get("/api/v1/payroll/preview/").status_code, 403)

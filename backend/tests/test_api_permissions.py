from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membership, User
from apps.core.models import AuditLog
from apps.inventory.models import StockBucket

from .helpers import World, client_for


class AuthTests(TestCase):
    def setUp(self):
        self.w = World()

    def test_unauthenticated_requests_are_rejected(self):
        c = APIClient()
        for url in ["/api/v1/locations/", "/api/v1/orders/", "/api/v1/stock/", "/api/v1/dashboard/", "/api/v1/settings/"]:
            self.assertIn(c.get(url).status_code, (401, 403), url)
        self.assertEqual(c.get("/api/v1/health/").status_code, 200)
        self.assertEqual(c.get("/api/v1/public-config/").status_code, 200)

    def test_login_logout_me(self):
        c = APIClient()
        bad = c.post("/api/v1/auth/login/", {"username": "owner", "password": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = c.post("/api/v1/auth/login/", {"username": "owner", "password": "ChangeMe-12345"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["is_superuser"])
        self.assertEqual(c.get("/api/v1/auth/me/").json()["username"], "owner")
        self.assertTrue(AuditLog.objects.filter(action="auth.login").exists())
        self.assertEqual(c.post("/api/v1/auth/logout/").status_code, 204)
        self.assertIn(c.get("/api/v1/auth/me/").status_code, (401, 403))

    def test_language_preference_is_saved_on_profile(self):
        c = client_for(self.w.cashier)
        self.assertEqual(c.patch("/api/v1/auth/me/", {"preferred_language": "ta"}, format="json").json()["preferred_language"], "ta")
        self.w.cashier.refresh_from_db()
        self.assertEqual(self.w.cashier.preferred_language, "ta")
        self.assertEqual(c.patch("/api/v1/auth/me/", {"preferred_language": "fr"}, format="json").status_code, 400)


class PermissionTests(TestCase):
    """Permissions are enforced in the backend, not just hidden in the UI."""

    def setUp(self):
        self.w = World()
        self.w.stock_raw()

    def test_cashier_cannot_create_production_batch(self):
        r = client_for(self.w.cashier).post("/api/v1/production-batches/", {"location": str(self.w.loc.id), "recipe": str(self.w.recipe.id), "quantity_produced": "10"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_production_manager_can_create_batch_via_api(self):
        r = client_for(self.w.prod_mgr).post("/api/v1/production-batches/", {"location": str(self.w.loc.id), "recipe": str(self.w.recipe.id), "quantity_produced": "100"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        rice = next(c for c in r.json()["consumptions"] if c["raw_material_name"] == "Rice")
        self.assertEqual(Decimal(rice["quantity"]), Decimal("40.000"))

    def test_location_isolation(self):
        # prod_mgr works at Sivakasi only; stock at the other unit must be invisible and un-writable
        self.w.stock_raw(self.w.loc2, qty=50)
        c = client_for(self.w.prod_mgr)
        ids = {row["location"] for row in c.get("/api/v1/stock/").json()["results"]}
        self.assertEqual(ids, {str(self.w.loc.id)})
        other = StockBucket.objects.filter(location=self.w.loc2).first()
        r = c.post("/api/v1/stock/adjust/", {"bucket": str(other.id), "movement_type": "wastage", "quantity_delta": "-1", "reason": "x"}, format="json")
        self.assertIn(r.status_code, (400, 403))
        r = c.post("/api/v1/production-batches/", {"location": str(self.w.loc2.id), "recipe": str(self.w.recipe.id), "quantity_produced": "10"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_owner_sees_all_locations(self):
        self.w.stock_raw(self.w.loc2, qty=50)
        ids = {row["location"] for row in client_for(self.w.owner).get("/api/v1/stock/").json()["results"]}
        self.assertEqual(ids, {str(self.w.loc.id), str(self.w.loc2.id)})

    def test_adjustment_requires_inventory_adjust_permission(self):
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice", location=self.w.loc)
        body = {"bucket": str(rice.id), "movement_type": "wastage", "quantity_delta": "-2", "reason": "spoiled"}
        self.assertEqual(client_for(self.w.cashier).post("/api/v1/stock/adjust/", body, format="json").status_code, 403)
        self.assertEqual(client_for(self.w.prod_mgr).post("/api/v1/stock/adjust/", body, format="json").status_code, 201)

    def test_only_owner_changes_settings(self):
        self.assertEqual(client_for(self.w.cashier).patch("/api/v1/settings/", {"gst_scheme": "composition"}, format="json").status_code, 403)
        r = client_for(self.w.owner).patch("/api/v1/settings/", {"gst_scheme": "composition"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="settings.update").exists())

    def test_audit_log_visible_only_with_permission(self):
        self.assertEqual(client_for(self.w.cashier).get("/api/v1/audit-logs/").status_code, 403)
        self.assertEqual(client_for(self.w.owner).get("/api/v1/audit-logs/").status_code, 200)

    def test_location_admin_cannot_grant_location_admin_role(self):
        admin = User.objects.create_user("locadmin", password="x-Pass12345")
        Membership.objects.create(user=admin, location=self.w.loc, role="location_admin")
        newbie = User.objects.create_user("newbie", password="x-Pass12345")
        r = client_for(admin).post("/api/v1/memberships/", {"user": str(newbie.id), "location": str(self.w.loc.id), "role": "location_admin"}, format="json")
        self.assertEqual(r.status_code, 403)
        r = client_for(admin).post("/api/v1/memberships/", {"user": str(newbie.id), "location": str(self.w.loc.id), "role": "production_employee"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        r = client_for(admin).post("/api/v1/memberships/", {"user": str(newbie.id), "location": str(self.w.loc2.id), "role": "production_employee"}, format="json")
        self.assertEqual(r.status_code, 403)  # not their location

    def test_business_rule_errors_return_400_with_message(self):
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice", location=self.w.loc)
        r = client_for(self.w.prod_mgr).post("/api/v1/stock/adjust/", {"bucket": str(rice.id), "movement_type": "wastage", "quantity_delta": "-99999", "reason": "oops"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Insufficient", r.json()["detail"])

    def test_payroll_hidden_from_non_payroll_roles(self):
        self.assertEqual(client_for(self.w.prod_mgr).get("/api/v1/payroll/").status_code, 403)
        self.assertEqual(client_for(self.w.cashier).get("/api/v1/payroll/").status_code, 200)

    def test_api_order_flow_end_to_end(self):
        self.w.make_packets(units=20)
        owner = client_for(self.w.owner)
        r = owner.post("/api/v1/orders/", {"customer": str(self.w.customer.id), "location": str(self.w.loc.id), "lines": [{"package": str(self.w.pkg1.id), "quantity": 3}], "delivery_address": str(self.w.address.id)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        oid = r.json()["id"]
        self.assertEqual(Decimal(r.json()["total"]), Decimal("165.00"))
        self.assertEqual(owner.post(f"/api/v1/orders/{oid}/confirm/").status_code, 200)
        self.assertEqual(owner.post(f"/api/v1/orders/{oid}/dispatch/").status_code, 200)
        inv = owner.get("/api/v1/invoices/").json()["results"][0]
        r = client_for(self.w.cashier).post("/api/v1/payments/record/", {"invoice": inv["id"], "method": "cash", "amount": "165", "tender_amount": "200"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()["change_returned"]), Decimal("35.00"))
        html = owner.get(f"/api/v1/invoices/{inv['id']}/print/")
        self.assertEqual(html.status_code, 200)
        self.assertIn(b"Tax Invoice", html.content)
        self.assertEqual(client_for(self.w.owner).get("/api/v1/orders/", {"status": "dispatched"}).json()["count"], 1)


class SalaryPrivacyTests(TestCase):
    def test_salary_fields_hidden_without_payroll_permission(self):
        from datetime import date

        from apps.hr.models import EmployeeProfile

        w = World()
        EmployeeProfile.objects.create(user=w.rider, location=w.loc, job_title="Rider", joining_date=date(2025, 1, 1), base_salary=Decimal("15000"))
        mgr_row = client_for(w.prod_mgr).get("/api/v1/employees/").json()["results"][0]
        self.assertNotIn("base_salary", mgr_row)
        owner_row = client_for(w.owner).get("/api/v1/employees/").json()["results"][0]
        self.assertEqual(owner_row["base_salary"], "15000.00")

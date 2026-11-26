from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Unit, convert
from apps.core.exceptions import BusinessRuleError, InsufficientStock
from apps.inventory import services as stock
from apps.inventory.models import RawMaterial, StockBucket, StockMovement
from apps.production import services as prod
from apps.purchasing import services as purch

from .helpers import World


class LedgerTests(TestCase):
    def setUp(self):
        self.w = World()

    def test_unit_conversion_and_density(self):
        l, kg, g = Unit.objects.get(code="l"), Unit.objects.get(code="kg"), Unit.objects.get(code="g")
        self.assertEqual(convert(Decimal("2"), l, Unit.objects.get(code="ml")), Decimal("2000"))
        self.assertEqual(convert(Decimal("500"), g, kg), Decimal("0.5"))
        self.assertEqual(convert(Decimal("100"), l, kg, product=self.w.idli), Decimal("105.000"))
        with self.assertRaises(BusinessRuleError):
            convert(Decimal("1"), l, kg)  # no density supplied

    def test_balance_never_negative(self):
        rm = RawMaterial.objects.get(name="Rice")
        bucket = stock.get_bucket(self.w.loc, "raw", raw_material=rm)
        stock.post_movement(bucket, Decimal("10"), "purchase", user=self.w.owner)
        with self.assertRaises(InsufficientStock):
            stock.post_movement(bucket, Decimal("-10.001"), "consumption", user=self.w.owner)
        bucket.refresh_from_db()
        self.assertEqual(bucket.quantity, Decimal("10.000"))

    def test_ledger_is_append_only_and_balance_matches_sum(self):
        self.w.stock_raw()
        mv = StockMovement.objects.first()
        with self.assertRaises(RuntimeError):
            mv.quantity_delta = 5
            mv.save()
        with self.assertRaises(RuntimeError):
            mv.delete()
        for b in StockBucket.objects.all():
            self.assertEqual(b.quantity, sum(m.quantity_delta for m in b.movements.all()))

    def test_purchase_cannot_be_received_twice(self):
        p = self.w.stock_raw()
        with self.assertRaises(BusinessRuleError):
            purch.receive_purchase(p, self.w.owner)
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice")
        self.assertEqual(rice.quantity, Decimal("500.000"))

    def test_adjustment_needs_reason_and_is_audited(self):
        self.w.stock_raw()
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice")
        with self.assertRaises(BusinessRuleError):
            stock.adjust_stock(rice, Decimal("-5"), "wastage", user=self.w.owner, reason=" ")
        stock.adjust_stock(rice, Decimal("-5"), "wastage", user=self.w.owner, reason="Spoiled in rain")
        from apps.core.models import AuditLog

        self.assertTrue(AuditLog.objects.filter(action="stock.wastage", reason="Spoiled in rain").exists())

    def test_transfer_moves_stock_between_locations(self):
        self.w.stock_raw()
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice", location=self.w.loc)
        stock.transfer_stock(rice, self.w.loc2, Decimal("30"), user=self.w.owner)
        rice.refresh_from_db()
        other = StockBucket.objects.get(kind="raw", raw_material__name="Rice", location=self.w.loc2)
        self.assertEqual((rice.quantity, other.quantity), (Decimal("470.000"), Decimal("30.000")))
        with self.assertRaises(BusinessRuleError):
            stock.transfer_stock(rice, self.w.loc, Decimal("1"), user=self.w.owner)


class ProductionTests(TestCase):
    def setUp(self):
        self.w = World()
        self.w.stock_raw()

    def test_recipe_consumes_raw_material_for_100_litres(self):
        batch = self.w.make_batch(100)
        qty = {c.raw_material.name: c.quantity for c in batch.consumptions.all()}
        self.assertEqual(qty["Rice"], Decimal("40.000"))
        self.assertEqual(qty["Urad dal"], Decimal("13.000"))
        self.assertEqual(qty["Fenugreek"], Decimal("0.500"))
        rice = StockBucket.objects.get(kind="raw", raw_material__name="Rice")
        self.assertEqual(rice.quantity, Decimal("460.000"))
        bulk = StockBucket.objects.get(kind="bulk", batch=batch)
        self.assertEqual(bulk.quantity, Decimal("100.000"))
        self.assertTrue(batch.batch_number.startswith("B-SVK-"))

    def test_half_batch_scales_consumption(self):
        batch = self.w.make_batch(50)
        self.assertEqual(batch.consumptions.get(raw_material__name="Rice").quantity, Decimal("20.000"))

    def test_production_fails_when_raw_material_short(self):
        with self.assertRaises(InsufficientStock):
            self.w.make_batch(5000)
        self.assertEqual(StockBucket.objects.get(kind="raw", raw_material__name="Rice").quantity, Decimal("500.000"))  # rolled back
        from apps.production.models import ProductionBatch

        self.assertEqual(ProductionBatch.objects.count(), 0)

    def test_packaging_moves_bulk_to_packed_without_double_counting(self):
        batch = self.w.make_packets(units=40)
        bulk = StockBucket.objects.get(kind="bulk", batch=batch)
        packed = StockBucket.objects.get(kind="packed", batch=batch)
        self.assertEqual((bulk.quantity, packed.quantity), (Decimal("60.000"), Decimal("40.000")))
        with self.assertRaises(InsufficientStock):
            prod.package_batch(user=self.w.prod_mgr, batch=batch, package=self.w.pkg2, units=40)  # needs 80 L, only 60 left

    def test_failed_quality_batch_cannot_be_packaged(self):
        batch = self.w.make_batch(10, quality_passed=False)
        with self.assertRaises(BusinessRuleError):
            prod.package_batch(user=self.w.prod_mgr, batch=batch, package=self.w.pkg1, units=5)

    def test_transfer_packed_stock_to_other_location(self):
        batch = self.w.make_packets(units=40)
        packed = StockBucket.objects.get(kind="packed", batch=batch)
        stock.transfer_stock(packed, self.w.loc2, Decimal("10"), user=self.w.owner)
        dest = StockBucket.objects.get(kind="packed", batch=batch, location=self.w.loc2)
        self.assertEqual(dest.quantity, Decimal("10.000"))
        self.assertEqual(dest.expiry_date, batch.expiry_date)

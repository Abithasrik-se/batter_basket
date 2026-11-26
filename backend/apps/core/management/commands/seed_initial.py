from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import Membership
from apps.catalog.models import Package, Price, Product, Unit
from apps.core.models import SystemSettings
from apps.inventory.models import RawMaterial
from apps.locations.models import Location
from apps.production.models import Recipe, RecipeLine

UNITS = [
    ("ml", "Millilitre", "மி.லி", "volume", "1"), ("l", "Litre", "லிட்டர்", "volume", "1000"),
    ("g", "Gram", "கிராம்", "weight", "1"), ("kg", "Kilogram", "கிலோ", "weight", "1000"),
    ("pcs", "Piece", "எண்ணிக்கை", "count", "1"),
]


class Command(BaseCommand):
    help = "Create units, settings, the Sivakasi location and (with --demo) sample products, recipe and staff."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create demo products, prices, recipe and demo users")
        parser.add_argument("--admin-password", default=None, help="Password for the 'owner' super admin (demo only)")

    def handle(self, *args, **opts):
        for code, name, ta, kind, factor in UNITS:
            Unit.objects.get_or_create(code=code, defaults=dict(name=name, name_ta=ta, kind=kind, factor=Decimal(factor)))
        s = SystemSettings.load()
        if not s.business_address:
            s.business_name = "Zeal Enterprises"
            s.business_address = "Sivakasi, Tamil Nadu"
            s.save()
        loc, _ = Location.objects.get_or_create(code="SVK", defaults=dict(name="Sivakasi Unit", address="Sivakasi, Tamil Nadu", latitude=Decimal("9.453300"), longitude=Decimal("77.802400")))
        self.stdout.write("Units, settings and Sivakasi location ready.")
        if not opts["demo"]:
            return

        User = get_user_model()
        owner, created = User.objects.get_or_create(username="owner", defaults=dict(is_staff=True, is_superuser=True, first_name="Owner"))
        if created or opts["admin_password"]:
            owner.set_password(opts["admin_password"] or "ChangeMe-12345")
            owner.save()
        litre, kg, pcs = Unit.objects.get(code="l"), Unit.objects.get(code="kg"), Unit.objects.get(code="pcs")
        ml = Unit.objects.get(code="ml")
        idli, _ = Product.objects.get_or_create(name="Idli Batter", defaults=dict(name_ta="இட்லி மாவு", product_type="idli", base_unit=litre, density_kg_per_litre=Decimal("1.050")))
        dosa, _ = Product.objects.get_or_create(name="Dosa Batter", defaults=dict(name_ta="தோசை மாவு", product_type="dosa", base_unit=litre, density_kg_per_litre=Decimal("1.030")))
        prices = {Decimal("0.5"): (28, 25, 23), Decimal("1"): (55, 50, 46), Decimal("2"): (105, 96, 88)}
        for product in (idli, dosa):
            for size, (hh, hotel, bulk) in prices.items():
                unit = ml if size < 1 else litre
                size_val = size * 1000 if size < 1 else size
                pkg, _ = Package.objects.get_or_create(product=product, size=size_val, unit=unit, defaults=dict(name=f"{size_val:g} ml" if size < 1 else f"{size:g} litre"))
                for group, amt in (("household", hh), ("hotel", hotel), ("bulk", bulk)):
                    Price.objects.get_or_create(package=pkg, price_group=group, effective_from=date(2024, 1, 1), defaults=dict(amount=Decimal(amt)))
        materials = {}
        for name, ta, unit, mn, pack in [("Rice", "அரிசி", kg, 100, False), ("Urad dal", "உளுந்து", kg, 40, False), ("Fenugreek", "வெந்தயம்", kg, 2, False), ("Salt", "உப்பு", kg, 5, False), ("Carry bags", "கேரி பைகள்", pcs, 200, True)]:
            materials[name], _ = RawMaterial.objects.get_or_create(name=name, defaults=dict(name_ta=ta, unit=unit, min_stock=mn, is_packaging=pack))
        recipe, made = Recipe.objects.get_or_create(product=idli, name="Standard idli batter (100 L)", defaults=dict(output_quantity=100))
        if made:
            for name, qty in (("Rice", 40), ("Urad dal", 13), ("Fenugreek", 0.5), ("Salt", 1.5)):
                RecipeLine.objects.create(recipe=recipe, raw_material=materials[name], quantity=Decimal(str(qty)), unit=kg)
        # Delivery charges (edit them in the app: Delivery -> Delivery charges)
        from apps.delivery.models import DeliveryFeeSlab, SurgeRule

        if not DeliveryFeeSlab.objects.filter(location=loc).exists():
            DeliveryFeeSlab.objects.create(location=loc, label="Nearby", min_km=0, max_km=3, base_fee=20)
            DeliveryFeeSlab.objects.create(location=loc, label="Town", min_km=3, max_km=8, base_fee=40, per_km_fee=0)
            DeliveryFeeSlab.objects.create(location=loc, label="Outskirts", min_km=8, max_km=None, base_fee=60, per_km_fee=5)
            SurgeRule.objects.create(location=loc, label="Busy day", min_orders=40, surcharge_type="percent", value=20)
        for username, role in [("prod_mgr", "production_manager"), ("cashier", "accountant"), ("rider1", "delivery_employee"), ("dispatch", "delivery_manager")]:
            u, c = User.objects.get_or_create(username=username, defaults=dict(first_name=username.replace("_", " ").title()))
            if c:
                u.set_password("ChangeMe-12345")
                u.save()
            Membership.objects.get_or_create(user=u, location=loc, role=role)
        self.stdout.write(self.style.SUCCESS("Demo data created. Login: owner / ChangeMe-12345 (change it!)."))

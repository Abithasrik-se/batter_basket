from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Membership
from apps.catalog.models import Package, Product
from apps.customers.models import Customer, CustomerAddress
from apps.inventory.models import RawMaterial
from apps.locations.models import Location
from apps.production import services as prod
from apps.production.models import Recipe
from apps.purchasing import services as purch
from apps.purchasing.models import Supplier

User = get_user_model()


class World:
    """Seeded demo data + a stocked Sivakasi unit, used by most tests."""

    def __init__(self):
        call_command("seed_initial", "--demo", stdout=__import__("io").StringIO())
        self.loc = Location.objects.get(code="SVK")
        self.loc2 = Location.objects.create(name="Second Unit", code="SEC")
        self.owner = User.objects.get(username="owner")
        self.prod_mgr = User.objects.get(username="prod_mgr")
        self.cashier = User.objects.get(username="cashier")
        self.rider = User.objects.get(username="rider1")
        self.dispatcher = User.objects.get(username="dispatch")
        self.idli = Product.objects.get(name="Idli Batter")
        self.pkg1 = Package.objects.get(product=self.idli, size=1, unit__code="l")
        self.pkg2 = Package.objects.get(product=self.idli, size=2, unit__code="l")
        self.recipe = Recipe.objects.get(product=self.idli)
        self.customer = Customer.objects.create(name="Lakshmi", phone="9000000001")
        self.hotel = Customer.objects.create(name="Hotel Saravana", phone="9000000002", category="hotel", price_group="hotel", discount_percent=Decimal("2"))
        self.address = CustomerAddress.objects.create(customer=self.customer, address_line="12 Main St, Sivakasi", is_default=True)

    def stock_raw(self, location=None, qty=500):
        location = location or self.loc
        sup, _ = Supplier.objects.get_or_create(name="Test Supplier")
        lines = [{"raw_material": rm, "quantity": Decimal(qty), "unit_cost": Decimal("10")} for rm in RawMaterial.objects.all()]
        p = purch.create_purchase(user=self.owner, supplier=sup, location=location, purchase_date=date.today(), lines=lines)
        purch.receive_purchase(p, self.owner)
        return p

    def make_batch(self, litres=100, location=None, **kw):
        return prod.create_batch(user=self.prod_mgr, location=location or self.loc, recipe=self.recipe, quantity_produced=Decimal(litres), **kw)

    def make_packets(self, units=40, litres=100, **kw):
        batch = self.make_batch(litres, **kw)
        prod.package_batch(user=self.prod_mgr, batch=batch, package=self.pkg1, units=units)
        return batch


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c

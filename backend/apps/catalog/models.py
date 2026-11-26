from decimal import Decimal

from django.db import models

from apps.core.exceptions import BusinessRuleError
from apps.core.models import BaseModel


class Unit(BaseModel):
    """Unit of measure. `factor` = how many base units (ml / g / piece) it contains."""

    KINDS = [("volume", "Volume"), ("weight", "Weight"), ("count", "Count")]

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=40)
    name_ta = models.CharField(max_length=40, blank=True)
    kind = models.CharField(max_length=10, choices=KINDS)
    factor = models.DecimalField(max_digits=14, decimal_places=6)

    class Meta:
        ordering = ["kind", "factor"]

    def __str__(self):
        return self.code


class Product(BaseModel):
    TYPES = [("idli", "Idli batter"), ("dosa", "Dosa batter"), ("other", "Other")]

    name = models.CharField(max_length=120)
    name_ta = models.CharField(max_length=120, blank=True)
    product_type = models.CharField(max_length=10, choices=TYPES, default="idli")
    description = models.TextField(blank=True)
    base_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+", help_text="Unit bulk batter is measured in (litre or kg)")
    density_kg_per_litre = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, help_text="Only needed to convert litres <-> kg")
    hsn_code = models.CharField(max_length=8, default="2106")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"), help_text="Confirm with your CA")
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Package(BaseModel):
    """A sellable pack size, e.g. 'Idli batter 1 litre'."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="packages")
    name = models.CharField(max_length=60, help_text="e.g. 1 litre")
    size = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__name", "size"]
        constraints = [models.UniqueConstraint(fields=["product", "size", "unit"], name="uniq_package_size")]

    def __str__(self):
        return f"{self.product.name} {self.name}"


class Price(BaseModel):
    """Selling price of a package for a price group, valid from/to a date."""

    GROUPS = [("household", "Household"), ("hotel", "Hotel"), ("bulk", "Bulk")]

    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="prices")
    price_group = models.CharField(max_length=10, choices=GROUPS, default="household")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="price_non_negative")]


def convert(quantity, from_unit: Unit, to_unit: Unit, *, product: Product | None = None) -> Decimal:
    """Convert between units. Volume<->weight only if the product has a density."""
    quantity = Decimal(quantity)
    if from_unit.pk == to_unit.pk:
        return quantity
    base = quantity * from_unit.factor  # ml / g / piece
    if from_unit.kind == to_unit.kind:
        return base / to_unit.factor
    if {from_unit.kind, to_unit.kind} == {"volume", "weight"} and product and product.density_kg_per_litre:
        density = product.density_kg_per_litre  # g per ml
        base = base * density if from_unit.kind == "volume" else base / density
        return base / to_unit.factor
    raise BusinessRuleError(f"Cannot convert {from_unit.code} to {to_unit.code}. Set a density on the product to convert litres and kg.")


def get_price(package: Package, price_group: str, on_date):
    """Price valid on `on_date`; falls back to the household price."""
    for group in (price_group, "household"):
        p = (
            Price.objects.filter(package=package, price_group=group, is_active=True, effective_from__lte=on_date)
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=on_date))
            .order_by("-effective_from")
            .first()
        )
        if p:
            return p.amount
    raise BusinessRuleError(f"No price configured for {package}.")

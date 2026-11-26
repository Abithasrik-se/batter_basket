"""Role-based access control.

A user has one Membership per (location, role). Roles map to permission codes.
Super admin (is_superuser) has every permission at every location.
"""

ALL_PERMISSIONS = [
    "locations.view", "locations.manage",
    "catalog.view", "catalog.manage",
    "inventory.view", "inventory.create", "inventory.adjust", "inventory.transfer",
    "purchasing.view", "purchasing.create", "purchasing.pay",
    "production.view", "production.create", "packaging.create",
    "customers.view", "customers.manage",
    "orders.view", "orders.create", "orders.confirm", "orders.dispatch", "orders.cancel", "orders.return",
    "billing.view", "payments.view", "payments.record", "payments.refund", "cash.close",
    "delivery.view", "delivery.assign", "delivery.record", "delivery.correct", "delivery.track", "delivery.fees",
    "employees.view", "employees.manage", "payroll.manage",
    "expenses.view", "expenses.create",
    "promotions.manage", "subscriptions.manage", "notifications.view",
    "reports.view", "audit.view", "settings.manage",
]

CUSTOMER_ROLE = "customer"

ROLE_PERMISSIONS = {
    "location_admin": set(ALL_PERMISSIONS) - {"settings.manage", "locations.manage"},
    "production_manager": {
        "locations.view", "catalog.view", "inventory.view", "inventory.adjust", "inventory.transfer",
        "production.view", "production.create", "packaging.create", "employees.view", "notifications.view",
    },
    "production_employee": {"locations.view", "catalog.view", "inventory.view", "production.view", "production.create", "packaging.create"},
    "inventory_manager": {
        "locations.view", "catalog.view", "inventory.view", "inventory.create", "inventory.adjust", "inventory.transfer",
        "purchasing.view", "purchasing.create", "notifications.view",
    },
    "accountant": {
        "locations.view", "catalog.view", "customers.view", "orders.view", "billing.view", "payments.view", "payments.record",
        "payments.refund", "cash.close", "expenses.view", "expenses.create", "purchasing.view", "purchasing.pay",
        "reports.view", "employees.view", "payroll.manage",
    },
    "delivery_manager": {
        "locations.view", "catalog.view", "customers.view", "orders.view", "orders.create", "orders.confirm", "orders.dispatch",
        "delivery.view", "delivery.assign", "delivery.track", "employees.view",
    },
    "delivery_employee": {"delivery.view", "delivery.record"},
    CUSTOMER_ROLE: set(),
}

ROLE_LABELS = {
    "location_admin": "Location Admin",
    "production_manager": "Production Manager",
    "production_employee": "Production Employee",
    "inventory_manager": "Inventory Manager",
    "accountant": "Accountant / Cashier",
    "delivery_manager": "Delivery Manager",
    "delivery_employee": "Delivery Employee",
    CUSTOMER_ROLE: "Customer",
}


def roles_granting(perm):
    return [role for role, perms in ROLE_PERMISSIONS.items() if perm in perms]


def user_has_perm(user, perm, location=None) -> bool:
    """True if `user` holds `perm` (optionally: at `location`)."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    qs = user.memberships.filter(is_active=True, role__in=roles_granting(perm))
    if location is not None:
        qs = qs.filter(location=location)
    return qs.exists()


def locations_with_perm(user, perm):
    """Queryset of locations where `user` holds `perm`."""
    from apps.locations.models import Location

    if not user or not user.is_authenticated or not user.is_active:
        return Location.objects.none()
    if user.is_superuser:
        return Location.objects.all()
    return Location.objects.filter(
        memberships__user=user, memberships__is_active=True, memberships__role__in=roles_granting(perm)
    ).distinct()


def permissions_for(user) -> dict:
    """{location_id: [perm, ...]} for the UI. Superuser -> every perm everywhere."""
    from apps.locations.models import Location

    if user.is_superuser:
        return {str(l.id): sorted(ALL_PERMISSIONS) for l in Location.objects.all()}
    out = {}
    for m in user.memberships.filter(is_active=True):
        out.setdefault(str(m.location_id), set()).update(ROLE_PERMISSIONS.get(m.role, ()))
    return {k: sorted(v) for k, v in out.items()}

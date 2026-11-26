from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import health

api = [
    path("health/", health, name="health"),
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.auth_urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.locations.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.purchasing.urls")),
    path("", include("apps.production.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.promotions.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.billing.urls")),
    path("", include("apps.delivery.urls")),
    path("", include("apps.hr.urls")),
    path("", include("apps.finance.urls")),
    path("", include("apps.subscriptions.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.dashboard.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

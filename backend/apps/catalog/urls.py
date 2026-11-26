from rest_framework.routers import DefaultRouter

from .views import PackageViewSet, PriceViewSet, ProductViewSet, UnitViewSet

router = DefaultRouter()
router.register("units", UnitViewSet, basename="unit")
router.register("products", ProductViewSet, basename="product")
router.register("packages", PackageViewSet, basename="package")
router.register("prices", PriceViewSet, basename="price")
urlpatterns = router.urls

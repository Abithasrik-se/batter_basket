from rest_framework.routers import DefaultRouter

from .views import RawMaterialViewSet, StockBucketViewSet, StockMovementViewSet

router = DefaultRouter()
router.register("raw-materials", RawMaterialViewSet, basename="raw-material")
router.register("stock", StockBucketViewSet, basename="stock")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")
urlpatterns = router.urls

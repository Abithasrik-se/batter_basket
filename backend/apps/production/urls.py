from rest_framework.routers import DefaultRouter

from .views import ProductionBatchViewSet, RecipeViewSet

router = DefaultRouter()
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("production-batches", ProductionBatchViewSet, basename="production-batch")
urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import HolidayViewSet, SubscriptionRunViewSet, SubscriptionViewSet

router = DefaultRouter()
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("subscription-runs", SubscriptionRunViewSet, basename="subscription-run")
router.register("holidays", HolidayViewSet, basename="holiday")
urlpatterns = router.urls

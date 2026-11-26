from rest_framework.routers import DefaultRouter

from .views import CouponViewSet, LoyaltyEntryViewSet, PromotionViewSet

router = DefaultRouter()
router.register("promotions", PromotionViewSet, basename="promotion")
router.register("coupons", CouponViewSet, basename="coupon")
router.register("loyalty", LoyaltyEntryViewSet, basename="loyalty")
urlpatterns = router.urls

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (DeliveryAssignmentViewSet, DeliveryFeeSlabViewSet, DeliveryRecordViewSet, DutyView, FeeQuoteView,
                    SurgeRuleViewSet, TrackingView)

router = DefaultRouter()
router.register("delivery/assignments", DeliveryAssignmentViewSet, basename="delivery-assignment")
router.register("delivery/records", DeliveryRecordViewSet, basename="delivery-record")
router.register("delivery/fee-slabs", DeliveryFeeSlabViewSet, basename="delivery-fee-slab")
router.register("delivery/surge-rules", SurgeRuleViewSet, basename="delivery-surge-rule")
urlpatterns = [path("delivery/duty/", DutyView.as_view()), path("delivery/quote/", FeeQuoteView.as_view()), path("delivery/tracking/", TrackingView.as_view())] + router.urls

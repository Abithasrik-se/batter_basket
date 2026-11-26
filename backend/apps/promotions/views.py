from rest_framework import viewsets

from apps.accounts.api import AuditedMixin, RBACViewSetMixin

from .models import Coupon, LoyaltyEntry, Promotion
from .serializers import CouponSerializer, LoyaltyEntrySerializer, PromotionSerializer


class PromoBase(RBACViewSetMixin, AuditedMixin, viewsets.ModelViewSet):
    perm_read = "customers.view"
    perm_write = "promotions.manage"
    location_field = None


class PromotionViewSet(PromoBase):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer


class CouponViewSet(PromoBase):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    search_fields = ["code"]


class LoyaltyEntryViewSet(RBACViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = LoyaltyEntry.objects.all()
    serializer_class = LoyaltyEntrySerializer
    perm_read = "customers.view"
    location_field = None
    filterset_fields = ["customer"]

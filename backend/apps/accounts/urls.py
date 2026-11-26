from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MembershipViewSet, RoleListView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("memberships", MembershipViewSet, basename="membership")
urlpatterns = [path("roles/", RoleListView.as_view())] + router.urls

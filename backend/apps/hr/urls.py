from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AttendanceViewSet, CheckInOutView, EmployeeProfileViewSet, PayrollEntryViewSet

router = DefaultRouter()
router.register("employees", EmployeeProfileViewSet, basename="employee")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("payroll", PayrollEntryViewSet, basename="payroll")
urlpatterns = [path("attendance-check/", CheckInOutView.as_view())] + router.urls

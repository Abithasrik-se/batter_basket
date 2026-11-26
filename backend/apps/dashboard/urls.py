from django.urls import path

from .views import DashboardView, SalesExportView

urlpatterns = [path("dashboard/", DashboardView.as_view()), path("dashboard/export-sales/", SalesExportView.as_view())]

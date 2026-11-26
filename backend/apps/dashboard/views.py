"""Owner dashboard. Every number is calculated from real transactions (invoices, payments,
ledger, batches), never from manually stored totals."""
import csv
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api import RBACPermission
from apps.accounts.rbac import locations_with_perm
from apps.billing.models import Invoice, Payment, Refund
from apps.billing.services import invoice_outstanding
from apps.catalog.models import Package
from apps.core.money import ZERO, q2, q3
from apps.customers.models import Customer
from apps.delivery.models import DeliveryAssignment
from apps.finance.models import Expense
from apps.hr.models import EmployeeProfile, PayrollEntry
from apps.inventory.models import RawMaterial, StockBucket
from apps.orders.models import Order, OrderLine
from apps.production.models import ProductionBatch
from apps.purchasing.models import Purchase


def _d(v):
    return str(q2(v or ZERO))


class BaseReportView(APIView):
    permission_classes = [RBACPermission]

    def required_permission(self, request):
        return "reports.view"

    def params(self, request):
        today = timezone.localdate()
        try:
            end = date.fromisoformat(request.query_params["to"]) if request.query_params.get("to") else today
            start = date.fromisoformat(request.query_params["from"]) if request.query_params.get("from") else end - timedelta(days=29)
        except ValueError:
            start, end = today - timedelta(days=29), today
        locs = locations_with_perm(request.user, "reports.view")
        if request.query_params.get("location"):
            locs = locs.filter(pk=request.query_params["location"])
        return start, end, locs


class DashboardView(BaseReportView):
    def get(self, request):
        start, end, locs = self.params(request)
        today = timezone.localdate()
        loc_ids = list(locs.values_list("id", flat=True))

        inv = Invoice.objects.filter(location__in=loc_ids)
        period_inv = inv.filter(issued_at__date__gte=start, issued_at__date__lte=end)
        net_sales = lambda qs: (qs.aggregate(t=Sum("total"))["t"] or ZERO) - (qs.aggregate(c=Sum("credit_total"))["c"] or ZERO)
        sales_today = net_sales(inv.filter(issued_at__date=today))
        revenue = net_sales(period_inv)
        revenue_ex_tax = (period_inv.aggregate(t=Sum("taxable_total"))["t"] or ZERO) + (period_inv.aggregate(t=Sum("delivery_fee"))["t"] or ZERO)

        trend = (
            period_inv.annotate(day=TruncDate("issued_at")).values("day").annotate(total=Sum("total")).order_by("day")
        )
        orders = Order.objects.filter(location__in=loc_ids, created_at__date__gte=start, created_at__date__lte=end)
        by_status = {r["status"]: r["n"] for r in orders.values("status").annotate(n=Count("id"))}

        batches = ProductionBatch.objects.filter(location__in=loc_ids, produced_at__date__gte=start, produced_at__date__lte=end)
        produced = batches.aggregate(t=Sum("quantity_produced"))["t"] or ZERO

        raw_low = []
        for rm in RawMaterial.objects.filter(is_active=True, min_stock__gt=0).select_related("unit"):
            for loc in locs:
                total = StockBucket.objects.filter(location=loc, kind="raw", raw_material=rm).aggregate(t=Sum("quantity"))["t"] or ZERO
                if total < rm.min_stock:
                    raw_low.append({"material": rm.name, "location": loc.name, "stock": str(total), "minimum": str(rm.min_stock), "unit": rm.unit.code})
        packed = [
            {"package": str(Package.objects.get(pk=r["package"])), "available": str(q3(r["a"]))}
            for r in StockBucket.objects.filter(location__in=loc_ids, kind="packed", quantity__gt=0).values("package").annotate(a=Sum(F("quantity") - F("reserved")))
        ]
        bulk_stock = StockBucket.objects.filter(location__in=loc_ids, kind="bulk").aggregate(t=Sum("quantity"))["t"] or ZERO
        expiring = StockBucket.objects.filter(location__in=loc_ids, kind__in=["packed", "bulk"], quantity__gt=0, expiry_date__lte=today + timedelta(days=1))
        expiring_rows = [{"item": b.item_name, "batch": b.batch.batch_number if b.batch else None, "expiry": str(b.expiry_date), "quantity": str(b.quantity), "expired": b.expiry_date < today} for b in expiring.select_related("batch", "package", "product", "package__product")]

        receivables = sum((max(invoice_outstanding(i), ZERO) for i in inv.select_related("order")), ZERO)
        payables = sum((p.balance for p in Purchase.objects.filter(location__in=loc_ids, status="received")), ZERO)

        collected = (Payment.objects.filter(invoice__location__in=loc_ids, received_at__date__gte=start, received_at__date__lte=end).aggregate(t=Sum("amount"))["t"] or ZERO) - (
            Refund.objects.filter(payment__invoice__location__in=loc_ids, refunded_at__date__gte=start, refunded_at__date__lte=end).aggregate(t=Sum("amount"))["t"] or ZERO
        )

        exp_rows = Expense.objects.filter(location__in=loc_ids, is_void=False, expense_date__gte=start, expense_date__lte=end)
        expenses = exp_rows.aggregate(t=Sum("amount"))["t"] or ZERO
        purchases_total = Purchase.objects.filter(location__in=loc_ids, status="received", purchase_date__gte=start, purchase_date__lte=end).aggregate(t=Sum("total"))["t"] or ZERO
        payroll = PayrollEntry.objects.filter(location__in=loc_ids, entry_type__in=["salary", "bonus"], period__gte=start, period__lte=end).aggregate(t=Sum("amount"))["t"] or ZERO
        total_expenses = expenses + purchases_total + payroll

        top = (
            OrderLine.objects.filter(order__location__in=loc_ids, order__created_at__date__gte=start, order__created_at__date__lte=end).exclude(order__status="cancelled")
            .values("package").annotate(qty=Sum("quantity"), amount=Sum("line_total")).order_by("-qty")[:5]
        )
        top_products = [{"package": str(Package.objects.select_related("product").get(pk=t["package"])), "quantity": t["qty"], "amount": _d(t["amount"])} for t in top]

        by_location = []
        for loc in locs:
            li = period_inv.filter(location=loc)
            by_location.append({
                "location": loc.name, "revenue": _d(net_sales(li)), "orders": orders.filter(location=loc).count(),
                "produced": _d(batches.filter(location=loc).aggregate(t=Sum("quantity_produced"))["t"]),
            })

        deliveries = DeliveryAssignment.objects.filter(location__in=loc_ids, created_at__date__gte=start, created_at__date__lte=end)
        customers = Customer.objects.filter(is_active=True)

        return Response({
            "period": {"from": str(start), "to": str(end)},
            "sales": {"today": _d(sales_today), "period": _d(revenue), "cash_collected": _d(collected), "trend": [{"date": str(t["day"]), "total": _d(t["total"])} for t in trend]},
            "orders": {"total": orders.count(), "pending": by_status.get("pending", 0) + by_status.get("confirmed", 0), "completed": by_status.get("completed", 0), "cancelled": by_status.get("cancelled", 0), "by_status": by_status},
            "production": {"total_batter": _d(produced), "batches": batches.count(), "bulk_stock": _d(bulk_stock)},
            "stock": {"packaged": packed, "raw_low": raw_low, "expiring": expiring_rows},
            "customers": {"total": customers.count(), "households": customers.filter(category="household").count(), "hotels": customers.filter(category="hotel").count(), "new_in_period": customers.filter(created_at__date__gte=start, created_at__date__lte=end).count()},
            "employees": {"active": EmployeeProfile.objects.filter(location__in=loc_ids, is_active=True).count()},
            "delivery": {"assigned": deliveries.count(), "delivered": deliveries.filter(status="delivered").count(), "failed": deliveries.filter(status="failed").count()},
            "finance": {
                "revenue": _d(revenue), "revenue_ex_tax": _d(revenue_ex_tax), "expenses": _d(total_expenses),
                "expense_breakdown": {"operating": _d(expenses), "raw_material_purchases": _d(purchases_total), "payroll": _d(payroll)},
                "operating_profit_estimate": _d(revenue_ex_tax - total_expenses), "receivables": _d(receivables), "payables": _d(payables),
                "note": "Operational estimate for management use. Not an audited financial statement.",
            },
            "top_products": top_products,
            "by_location": by_location,
        })


class SalesExportView(BaseReportView):
    """CSV export of invoices in the period."""

    def get(self, request):
        start, end, locs = self.params(request)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="sales_{start}_{end}.csv"'
        w = csv.writer(resp)
        w.writerow(["Invoice", "Date", "Location", "Customer", "Type", "Taxable", "CGST", "SGST", "Delivery", "Total", "Credit", "Outstanding"])
        for i in Invoice.objects.filter(location__in=locs, issued_at__date__gte=start, issued_at__date__lte=end).select_related("customer", "location", "order").order_by("issued_at"):
            w.writerow([i.invoice_number, timezone.localtime(i.issued_at).date(), i.location.name, i.customer.name, i.invoice_type, i.taxable_total, i.cgst, i.sgst, i.delivery_fee, i.total, i.credit_total, invoice_outstanding(i)])
        return resp

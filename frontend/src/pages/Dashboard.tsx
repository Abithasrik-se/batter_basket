import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Banknote, Boxes, CheckCircle2, Clock, Factory, HandCoins, Plus, Receipt, ShoppingCart, TrendingUp, Wallet, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, HelpBanner, PageHeader } from "../components/ui";
import { api, errorMessage, Page } from "../lib/api";
import { money, num } from "../lib/format";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type D = any;

function Stat({ icon: Icon, label, value, hint, tone }: { icon: LucideIcon; label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="card relative overflow-hidden" title={hint}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[11px] font-semibold uppercase tracking-wider text-muted">{label}</div>
          <div className={`mt-1 truncate text-xl font-bold tabular-nums sm:text-2xl ${tone ?? ""}`}>{value}</div>
        </div>
        <div className="rounded-lg bg-accent/15 p-2 text-accent"><Icon size={18} /></div>
      </div>
      {hint && <div className="mt-1.5 line-clamp-2 text-xs text-muted">{hint}</div>}
    </div>
  );
}

function Bars({ rows }: { rows: { date: string; total: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => Number(r.total)));
  return (
    <div className="flex h-44 items-end gap-1 pt-6" role="img" aria-label="sales trend">
      {rows.map((r) => (
        <div key={r.date} className="group relative flex h-full flex-1 items-end">
          <div className="w-full rounded-t bg-gradient-to-t from-accent to-accent/60 transition group-hover:brightness-110" style={{ height: `${Math.max(3, (Number(r.total) / max) * 100)}%` }} />
          <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-primary px-2 py-1 text-xs text-primary-foreground group-hover:block">{r.date}: {money(r.total)}</div>
        </div>
      ))}
    </div>
  );
}

function Row({ left, right, tone }: { left: ReactNode; right: ReactNode; tone?: string }) {
  return <div className={`flex items-center justify-between gap-3 border-b border-border py-2 text-sm last:border-0 ${tone ?? ""}`}><span className="min-w-0 truncate">{left}</span><span className="shrink-0 font-medium tabular-nums">{right}</span></div>;
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const [location, setLocation] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const params = { ...(location && { location }), ...(from && { from }), ...(to && { to }) };
  const locs = useQuery({ queryKey: ["locations", "all"], queryFn: async () => (await api.get<Page<{ id: string; name: string }>>("/locations/")).data.results });
  const q = useQuery({ queryKey: ["dashboard", params], queryFn: async () => (await api.get<D>("/dashboard/", { params })).data });
  const d = q.data;
  const exportUrl = `/api/v1/dashboard/export-sales/?${new URLSearchParams(params as Record<string, string>)}`;
  const quick = [
    { to: "/orders", label: t("orders:new"), perm: "orders.create", icon: ShoppingCart }, { to: "/production", label: t("production:new"), perm: "production.create", icon: Factory },
    { to: "/purchases", label: t("inventory:newPurchase"), perm: "purchasing.create", icon: Boxes }, { to: "/expenses", label: t("common:nav.expenses"), perm: "expenses.create", icon: Wallet },
  ].filter((x) => can(x.perm));

  return (
    <div className="space-y-5">
      <PageHeader title={t("dashboard:title")} subtitle={t("hints:page.dashboardSub")} actions={<a className="btn-outline" href={exportUrl}><Receipt size={16} />{t("dashboard:export")}</a>} />
      <HelpBanner id="dashboard" text="hints:page.dashboard" />
      {quick.length > 0 && <div className="flex flex-wrap gap-2">{quick.map((x) => { const I = x.icon; return <Link key={x.to} to={x.to} className="btn-outline"><Plus size={14} /><I size={16} />{x.label}</Link>; })}</div>}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select className="input" value={location} onChange={(e) => setLocation(e.target.value)} aria-label={t("common:f.location")}>
          <option value="">{t("dashboard:allLocations")}</option>
          {locs.data?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-muted"><span className="w-12 shrink-0">{t("dashboard:from")}</span><input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm text-muted"><span className="w-12 shrink-0">{t("dashboard:to")}</span><input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      </div>

      {q.isLoading ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton h-24" />)}</div>
        : q.isError ? <ErrorBox message={errorMessage(q.error)} /> : d && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat icon={TrendingUp} label={t("dashboard:salesToday")} value={money(d.sales.today)} hint={t("hints:dash.salesToday")} />
            <Stat icon={Banknote} label={t("dashboard:salesPeriod")} value={money(d.sales.period)} hint={t("hints:dash.salesPeriod")} />
            <Stat icon={HandCoins} label={t("dashboard:cashCollected")} value={money(d.sales.cash_collected)} hint={t("hints:dash.cashCollected")} />
            <Stat icon={Clock} label={t("dashboard:receivables")} value={money(d.finance.receivables)} tone="text-warning" hint={t("hints:dash.receivables")} />
            <Stat icon={ShoppingCart} label={t("dashboard:ordersTotal")} value={d.orders.total} />
            <Stat icon={Clock} label={t("dashboard:ordersPending")} value={d.orders.pending} hint={t("hints:dash.pending")} />
            <Stat icon={CheckCircle2} label={t("dashboard:ordersCompleted")} value={d.orders.completed} />
            <Stat icon={XCircle} label={t("dashboard:ordersCancelled")} value={d.orders.cancelled} />
            <Stat icon={Factory} label={t("dashboard:batterProduced")} value={`${num(d.production.total_batter)} L`} />
            <Stat icon={Boxes} label={t("dashboard:bulkStock")} value={`${num(d.production.bulk_stock)} L`} hint={t("hints:dash.bulk")} />
            <Stat icon={Wallet} label={t("dashboard:expenses")} value={money(d.finance.expenses)} hint={t("hints:dash.expenses")} />
            <Stat icon={TrendingUp} label={t("dashboard:profitEstimate")} value={money(d.finance.operating_profit_estimate)} tone={Number(d.finance.operating_profit_estimate) < 0 ? "text-danger" : "text-success"} hint={t("dashboard:profitNote")} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card"><h2 className="font-semibold">{t("dashboard:trend")}</h2>{d.sales.trend.length ? <Bars rows={d.sales.trend} /> : <p className="py-8 text-center text-sm text-muted">{t("common:empty")}</p>}</div>
            <div className="card"><h2 className="mb-1 font-semibold">{t("dashboard:topProducts")}</h2>
              {d.top_products.map((p: D) => <Row key={p.package} left={p.package} right={`${p.quantity} · ${money(p.amount)}`} />)}
              {!d.top_products.length && <p className="py-6 text-center text-sm text-muted">{t("common:empty")}</p>}</div>
            <div className="card"><h2 className="mb-1 font-semibold">{t("dashboard:packagedStock")}</h2>
              {d.stock.packaged.map((p: D) => <Row key={p.package} left={p.package} right={num(p.available)} />)}
              {!d.stock.packaged.length && <p className="py-6 text-center text-sm text-muted">{t("common:empty")}</p>}</div>
            <div className="card"><h2 className="mb-1 flex items-center gap-2 font-semibold"><AlertTriangle size={16} className="text-warning" />{t("dashboard:alerts")}</h2>
              {d.stock.raw_low.map((r: D, i: number) => <Row key={i} tone="text-danger" left={t("dashboard:lowStock", { item: r.material, stock: r.stock, unit: r.unit, min: r.minimum })} right="" />)}
              {d.stock.expiring.map((r: D, i: number) => <Row key={`e${i}`} tone="text-warning" left={`${r.item} ${r.batch ?? ""}`} right={`${r.expiry}${r.expired ? ` (${t("dashboard:expired")})` : ""}`} />)}
              {!d.stock.raw_low.length && !d.stock.expiring.length && <p className="py-6 text-center text-sm text-muted">✓ {t("dashboard:noAlerts")}</p>}</div>
            <div className="card"><h2 className="mb-2 font-semibold">{t("dashboard:customers")}</h2>
              <p className="text-sm">{t("dashboard:customerStats", { total: d.customers.total, households: d.customers.households, hotels: d.customers.hotels, fresh: d.customers.new_in_period })}</p>
              <p className="mt-2 text-sm">{t("dashboard:deliveryStats", { assigned: d.delivery.assigned, delivered: d.delivery.delivered, failed: d.delivery.failed })}</p>
              <p className="mt-2 text-sm">{t("dashboard:employeeStats", { count: d.employees.active })}</p></div>
            <div className="card"><h2 className="mb-1 font-semibold">{t("dashboard:byLocation")}</h2>
              {d.by_location.map((l: D) => <Row key={l.location} left={l.location} right={`${money(l.revenue)} · ${l.orders} · ${num(l.produced)} L`} />)}</div>
          </div>
        </>
      )}
    </div>
  );
}

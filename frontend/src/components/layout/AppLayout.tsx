import {
  BarChart3, Banknote, Boxes, CalendarCheck, ChevronDown, ClipboardList, Factory, FileText, LayoutDashboard, LogOut, Menu, Moon, Package, ShoppingCart, Sun, Truck, Users, Wallet, X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { setMode } from "../../theme/applyTheme";
import AttendanceWidget from "../AttendanceWidget";
import LanguageSwitch from "../LanguageSwitch";

export interface NavItem { to: string; label: string; perm: string }
interface Group { id: string; label: string; icon: LucideIcon; items: NavItem[] }

/** perm "@staff" = visible to anyone who works at a location (employee self-service). */
export const NAV: Group[] = [
  { id: "overview", label: "common:groups.overview", icon: LayoutDashboard, items: [{ to: "/", label: "common:nav.dashboard", perm: "reports.view" }] },
  { id: "sales", label: "common:groups.sales", icon: ShoppingCart, items: [
    { to: "/orders", label: "common:nav.orders", perm: "orders.view" }, { to: "/invoices", label: "common:nav.invoices", perm: "billing.view" },
    { to: "/cash-closing", label: "common:nav.cashClosing", perm: "payments.view" }, { to: "/subscriptions", label: "common:nav.subscriptions", perm: "orders.view" },
    { to: "/holidays", label: "common:nav.holidays", perm: "orders.view" },
  ] },
  { id: "customers", label: "common:groups.customers", icon: Users, items: [
    { to: "/customers", label: "common:nav.customers", perm: "customers.view" }, { to: "/addresses", label: "common:nav.addresses", perm: "customers.view" },
    { to: "/promotions", label: "common:nav.promotions", perm: "customers.view" }, { to: "/coupons", label: "common:nav.coupons", perm: "customers.view" },
  ] },
  { id: "production", label: "common:groups.production", icon: Factory, items: [
    { to: "/production", label: "common:nav.production", perm: "production.view" }, { to: "/recipes", label: "common:nav.recipes", perm: "production.view" },
  ] },
  { id: "stock", label: "common:groups.stock", icon: Boxes, items: [
    { to: "/stock", label: "common:nav.stock", perm: "inventory.view" }, { to: "/ledger", label: "common:nav.ledger", perm: "inventory.view" },
    { to: "/raw-materials", label: "common:nav.rawMaterials", perm: "inventory.view" }, { to: "/purchases", label: "common:nav.purchases", perm: "purchasing.view" },
    { to: "/suppliers", label: "common:nav.suppliers", perm: "purchasing.view" },
  ] },
  { id: "delivery", label: "common:groups.delivery", icon: Truck, items: [
    { to: "/delivery", label: "common:nav.delivery", perm: "delivery.view" }, { to: "/delivery-charges", label: "common:nav.deliveryCharges", perm: "delivery.view" },
  ] },
  { id: "catalog", label: "common:groups.catalog", icon: Package, items: [
    { to: "/products", label: "common:nav.products", perm: "catalog.view" }, { to: "/packages", label: "common:nav.packages", perm: "catalog.view" },
    { to: "/prices", label: "common:nav.prices", perm: "catalog.view" }, { to: "/units", label: "common:nav.units", perm: "catalog.view" },
  ] },
  { id: "people", label: "common:groups.people", icon: CalendarCheck, items: [
    { to: "/my-attendance", label: "common:nav.myAttendance", perm: "@staff" }, { to: "/attendance", label: "common:nav.attendance", perm: "employees.view" },
    { to: "/employees", label: "common:nav.employees", perm: "employees.view" }, { to: "/payroll", label: "common:nav.payroll", perm: "payroll.manage" },
    { to: "/users", label: "common:nav.users", perm: "employees.view" }, { to: "/access", label: "common:nav.access", perm: "employees.view" },
  ] },
  { id: "finance", label: "common:groups.finance", icon: Wallet, items: [{ to: "/expenses", label: "common:nav.expenses", perm: "expenses.view" }] },
  { id: "admin", label: "common:groups.admin", icon: ClipboardList, items: [
    { to: "/locations", label: "common:nav.locations", perm: "locations.view" }, { to: "/audit", label: "common:nav.audit", perm: "audit.view" }, { to: "/settings", label: "common:nav.settings", perm: "settings.manage" },
  ] },
];

const BOTTOM: { to: string; label: string; perm: string; icon: LucideIcon }[] = [
  { to: "/", label: "common:nav.dashboard", perm: "reports.view", icon: BarChart3 },
  { to: "/orders", label: "common:nav.orders", perm: "orders.view", icon: ShoppingCart },
  { to: "/production", label: "common:nav.production", perm: "production.view", icon: Factory },
  { to: "/stock", label: "common:nav.stock", perm: "inventory.view", icon: Boxes },
  { to: "/delivery", label: "common:nav.delivery", perm: "delivery.view", icon: Truck },
  { to: "/invoices", label: "common:nav.invoices", perm: "billing.view", icon: FileText },
  { to: "/my-attendance", label: "common:nav.myAttendance", perm: "@staff", icon: Banknote },
];

export default function AppLayout() {
  const { t } = useTranslation();
  const { me, can, logout } = useAuth();
  const loc = useLocation();
  const [drawer, setDrawer] = useState(false);
  const [dark, setDark] = useState(document.documentElement.dataset.theme === "dark");
  const allowed = (perm: string) => (perm === "@staff" ? !!me && me.roles.length > 0 : can(perm));
  const groups = useMemo(() => NAV.map((g) => ({ ...g, items: g.items.filter((i) => allowed(i.perm)) })).filter((g) => g.items.length), [me]); // eslint-disable-line react-hooks/exhaustive-deps
  const activeGroup = groups.find((g) => g.items.some((i) => (i.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(i.to))))?.id;
  const [open, setOpen] = useState<Record<string, boolean>>({});
  useEffect(() => { if (activeGroup) setOpen((o) => ({ ...o, [activeGroup]: true })); }, [activeGroup]);
  useEffect(() => setDrawer(false), [loc.pathname]);
  const bottom = BOTTOM.filter((b) => allowed(b.perm)).slice(0, 4);

  const nav = (
    <nav className="space-y-1 p-3" aria-label="Main">
      {groups.map((g) => {
        const Icon = g.icon;
        const isOpen = !!open[g.id];
        const single = g.items.length === 1;
        return (
          <div key={g.id}>
            {single ? (
              <NavLink to={g.items[0].to} end className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${isActive ? "bg-accent font-semibold text-accent-foreground" : "text-primary-foreground/85 hover:bg-white/10"}`}>
                <Icon size={18} />{t(g.items[0].label)}
              </NavLink>
            ) : (
              <>
                <button onClick={() => setOpen({ ...open, [g.id]: !isOpen })} aria-expanded={isOpen}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${g.id === activeGroup ? "text-accent" : "text-primary-foreground/85"} hover:bg-white/10`}>
                  <Icon size={18} /><span className="flex-1 text-left font-medium">{t(g.label)}</span>
                  <ChevronDown size={15} className={`transition ${isOpen ? "rotate-180" : ""}`} />
                </button>
                {isOpen && (
                  <div className="ml-5 mt-0.5 space-y-0.5 border-l border-white/15 pl-3">
                    {g.items.map((i) => (
                      <NavLink key={i.to} to={i.to} end={i.to === "/"} className={({ isActive }) => `block rounded-md px-3 py-2 text-[13px] ${isActive ? "bg-accent font-semibold text-accent-foreground" : "text-primary-foreground/75 hover:bg-white/10 hover:text-primary-foreground"}`}>
                        {t(i.label)}
                      </NavLink>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-dvh lg:flex">
      <aside className={`fixed inset-y-0 left-0 z-40 w-72 max-w-[85vw] overflow-y-auto bg-primary shadow-2xl transition-transform lg:static lg:w-64 lg:max-w-none lg:translate-x-0 lg:shadow-none ${drawer ? "translate-x-0" : "-translate-x-full"}`} style={{ paddingTop: "env(safe-area-inset-top)" }}>
        <div className="flex items-center gap-3 border-b border-white/10 p-4">
          <img src="/logo-mark.png" alt="" className="h-10 rounded-lg bg-white p-0.5" />
          <div className="min-w-0 flex-1"><div className="truncate font-semibold text-primary-foreground">{t("common:app.name")}</div><div className="text-[11px] uppercase tracking-widest text-accent">{t("common:app.tag")}</div></div>
          <button className="text-primary-foreground lg:hidden" aria-label="close menu" onClick={() => setDrawer(false)}><X size={20} /></button>
        </div>
        {nav}
        <div className="border-t border-white/10 p-3 lg:hidden"><LanguageSwitch /></div>
      </aside>
      {drawer && <div className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden" onClick={() => setDrawer(false)} />}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-border bg-surface/90 px-3 py-2 backdrop-blur sm:gap-3 sm:px-5" style={{ paddingTop: "max(0.5rem, env(safe-area-inset-top))" }}>
          <button className="btn-ghost !px-2 lg:hidden" aria-label="menu" onClick={() => setDrawer(true)}><Menu size={22} /></button>
          <div className="flex-1" />
          {me && me.roles.length > 0 && <AttendanceWidget compact />}
          <div className="hidden sm:block"><LanguageSwitch /></div>
          <button className="btn-ghost !px-2" aria-label="toggle theme" onClick={() => { const next = dark ? "light" : "dark"; setMode(next); setDark(!dark); }}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          <span className="hidden max-w-[10rem] truncate text-sm text-muted md:inline">{me?.name}</span>
          <button className="btn-ghost !px-2" aria-label={t("common:actions.logout")} onClick={logout}><LogOut size={18} /></button>
        </header>
        <main className="mx-auto max-w-7xl p-3 pb-28 sm:p-5 lg:p-6 lg:pb-8"><Outlet /></main>
      </div>

      {/* phones: thumb-reach tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid border-t border-border bg-surface/95 backdrop-blur lg:hidden" style={{ gridTemplateColumns: `repeat(${bottom.length + 1}, 1fr)`, paddingBottom: "env(safe-area-inset-bottom)" }} aria-label="Quick">
        {bottom.map((b) => {
          const Icon = b.icon;
          return (
            <NavLink key={b.to} to={b.to} end={b.to === "/"} className={({ isActive }) => `flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] ${isActive ? "font-semibold text-accent" : "text-muted"}`}>
              <Icon size={20} /><span className="max-w-full truncate px-1">{t(b.label)}</span>
            </NavLink>
          );
        })}
        <button className="flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] text-muted" onClick={() => setDrawer(true)}><Menu size={20} />{t("common:nav.more")}</button>
      </nav>
    </div>
  );
}

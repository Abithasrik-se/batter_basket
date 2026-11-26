import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import AppLayout, { NAV } from "./components/layout/AppLayout";
import ResourcePage, { ResourceConfig } from "./components/ResourcePage";
import { Spinner } from "./components/ui";
import { api } from "./lib/api";
import Dashboard from "./pages/Dashboard";
import DeliveryChargesPage from "./pages/DeliveryChargesPage";
import DeliveryPage from "./pages/DeliveryPage";
import Login from "./pages/Login";
import MyAttendance from "./pages/MyAttendance";
import PayrollPage from "./pages/PayrollPage";
import * as R from "./pages/resources";
import Settings from "./pages/Settings";
import { applyThemeOverrides } from "./theme/applyTheme";

const page = (cfg: ResourceConfig) => <ResourcePage cfg={cfg} />;

function Landing() {
  const { can } = useAuth();
  const first = NAV.flatMap((g) => g.items).find((i) => can(i.perm));
  return first ? <Navigate to={first.to} replace /> : <div className="p-6">No access has been assigned to this account yet.</div>;
}

export default function App() {
  const { me, loading, can } = useAuth();
  const cfg = useQuery({ queryKey: ["public-config"], queryFn: async () => (await api.get("/public-config/")).data, staleTime: 5 * 60_000 });
  useEffect(() => { applyThemeOverrides(cfg.data?.theme); }, [cfg.data]);

  if (loading) return <Spinner />;
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {me ? (
        <Route element={<AppLayout />}>
          <Route index element={can("reports.view") ? <Dashboard /> : <Landing />} />
          <Route path="orders" element={page(R.orders)} />
          <Route path="invoices" element={page(R.invoices)} />
          <Route path="cash-closing" element={page(R.cashClosings)} />
          <Route path="subscriptions" element={page(R.subscriptions)} />
          <Route path="customers" element={page(R.customers)} />
          <Route path="addresses" element={page(R.customerAddresses)} />
          <Route path="promotions" element={page(R.promotions)} />
          <Route path="coupons" element={page(R.coupons)} />
          <Route path="production" element={page(R.productionBatches)} />
          <Route path="recipes" element={page(R.recipes)} />
          <Route path="stock" element={page(R.stock)} />
          <Route path="ledger" element={page(R.stockMovements)} />
          <Route path="raw-materials" element={page(R.rawMaterials)} />
          <Route path="purchases" element={page(R.purchases)} />
          <Route path="suppliers" element={page(R.suppliers)} />
          <Route path="delivery" element={<DeliveryPage />} />
          <Route path="products" element={page(R.products)} />
          <Route path="packages" element={page(R.packages)} />
          <Route path="prices" element={page(R.prices)} />
          <Route path="expenses" element={page(R.expenses)} />
          <Route path="employees" element={page(R.employees)} />
          <Route path="payroll" element={<PayrollPage />} />
          <Route path="attendance" element={page(R.attendance)} />
          <Route path="my-attendance" element={<MyAttendance />} />
          <Route path="delivery-charges" element={<DeliveryChargesPage />} />
          <Route path="holidays" element={page(R.holidays)} />
          <Route path="units" element={page(R.units)} />
          <Route path="users" element={page(R.users)} />
          <Route path="access" element={page(R.memberships)} />
          <Route path="locations" element={page(R.locations)} />
          <Route path="audit" element={page(R.auditLogs)} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      ) : (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  );
}

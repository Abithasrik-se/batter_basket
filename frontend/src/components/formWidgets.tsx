import { useQuery } from "@tanstack/react-query";
import { MapPin, Plus, Truck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../lib/api";
import { money, num } from "../lib/format";
import { useFeedback } from "./feedback";
import { FormModal, Row } from "./ResourcePage";
import { useQueryClient } from "@tanstack/react-query";

/** Live delivery charge preview inside the order form (distance slab + busy-day surge + free-delivery rule). */
export function FeeQuote({ values }: { values: Row }) {
  const { t } = useTranslation();
  const lines = (values.lines ?? []).filter((l: Row) => l.package && Number(l.quantity) > 0).map((l: Row) => ({ package: l.package, quantity: Number(l.quantity) }));
  const q = useQuery({
    queryKey: ["fee-quote", values.location, values.delivery_address, values.scheduled_date, JSON.stringify(lines)],
    enabled: !!values.location && !!values.delivery_address,
    retry: false,
    queryFn: async () => (await api.post("/delivery/quote/", { location: values.location, delivery_address: values.delivery_address, scheduled_date: values.scheduled_date || undefined, lines })).data,
  });
  if (!values.location || !values.delivery_address) return <div className="mt-4 rounded-xl border border-dashed border-border p-3 text-xs text-muted">{t("hints:order.feeWaiting")}</div>;
  if (q.isError) return <div className="mt-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{errorMessage(q.error)}</div>;
  const d = q.data;
  if (!d) return <div className="skeleton mt-4 h-20" />;
  return (
    <div className="mt-4 rounded-xl border border-accent/40 bg-accent/5 p-3 text-sm">
      <div className="flex items-center justify-between font-semibold"><span className="flex items-center gap-2"><Truck size={16} className="text-accent" />{t("hints:order.feeTitle")}</span><span className="text-base">{Number(d.total) === 0 ? t("hints:order.free") : money(d.total)}</span></div>
      <ul className="mt-1.5 space-y-0.5 text-xs text-muted">
        {d.distance_km && <li>{t("hints:order.feeDistance", { km: d.distance_km, base: money(d.base_fee) })}</li>}
        {Number(d.surge_amount) > 0 && <li>{t("hints:order.feeSurge", { amount: money(d.surge_amount), rule: d.surge_rule, n: d.orders_that_day })}</li>}
        {d.notes.includes("distance_unknown") && <li className="text-warning">{t("hints:order.feeNoPin", { base: money(d.base_fee) })}</li>}
        {d.notes.includes("no_slab") && <li className="text-warning">{t("hints:order.feeNoSlab")}</li>}
        {d.notes.includes("free_delivery") && <li className="text-success">{t("hints:order.feeFree", { amount: money(d.free_delivery_above) })}</li>}
      </ul>
    </div>
  );
}

/** Add an address (with a map pin) without leaving the order form. */
export function QuickAddress({ values, setValues }: { values: Row; setValues: (v: Row) => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const fb = useFeedback();
  const [open, setOpen] = useState(false);
  if (!values.customer) return null;
  return (
    <>
      <button type="button" className="btn-outline btn-sm mt-2" onClick={() => setOpen(true)}><Plus size={14} /><MapPin size={14} />{t("hints:order.newAddress")}</button>
      {open && (
        <FormModal title={t("hints:order.newAddress")} onClose={() => setOpen(false)}
          fields={[
            { name: "address_line", label: "common:f.address", type: "textarea", required: true },
            { name: "pincode", label: "masters:f.pincode", type: "text" },
            { name: "pin", label: "masters:f.pin", type: "map", hint: "hints:field.pin" },
          ]}
          onSubmit={async (v) => {
            const body: Row = { customer: values.customer, label: "Delivery", ...Object.fromEntries(Object.entries(v).filter(([, x]) => x !== "")) };
            const { data } = await api.post("/customer-addresses/", body);
            await qc.invalidateQueries({ queryKey: ["options"] });
            setValues({ ...values, delivery_address: data.id });
            fb.success(t("common:saved"));
          }} />
      )}
    </>
  );
}

/** Shows what a batch will use and whether stock covers it. */
export function RecipeRequirements({ values }: { values: Row }) {
  const { t } = useTranslation();
  const qty = Number(values.quantity_produced);
  const q = useQuery({
    queryKey: ["recipe-req", values.recipe, values.location, qty],
    enabled: !!values.recipe && qty > 0,
    queryFn: async () => (await api.get(`/recipes/${values.recipe}/requirements/`, { params: { quantity: qty, location: values.location || undefined } })).data,
  });
  if (!values.recipe || !(qty > 0)) return <div className="mt-4 rounded-xl border border-dashed border-border p-3 text-xs text-muted">{t("hints:batch.waiting")}</div>;
  const lines: { material: string; unit: string; needed: string; in_stock: string | null; short: string | null }[] = q.data?.lines ?? [];
  return (
    <div className="mt-4 rounded-xl border border-border p-3 text-sm">
      <div className="mb-1.5 font-semibold">{t("hints:batch.uses", { qty })}</div>
      {lines.map((l) => {
        const short = l.short && Number(l.short) > 0;
        return <div key={l.material} className={`flex justify-between gap-2 border-b border-border py-1 text-xs last:border-0 ${short ? "text-danger" : ""}`}><span>{l.material}</span><span className="tabular-nums">{num(l.needed)} {l.unit}{l.in_stock != null && ` / ${num(l.in_stock)} ${t("hints:batch.inStock")}`}{short ? ` ⚠ ${t("hints:batch.short", { n: num(l.short) })}` : ""}</span></div>;
      })}
    </div>
  );
}

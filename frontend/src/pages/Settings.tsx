import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useFeedback } from "../components/feedback";
import { ErrorBox, HelpBanner, Hint, PageHeader, Spinner } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { applyThemeOverrides } from "../theme/applyTheme";

const COLOURS = ["primary", "accent", "background", "surface", "text"] as const;
const DEFAULTS: Record<string, string> = { primary: "#0B0B0B", accent: "#C9971C", background: "#FAF9F6", surface: "#FFFFFF", text: "#141414" };
const KEYS = ["business_name", "business_address", "business_phone", "business_email", "gstin", "gst_scheme", "prices_include_tax", "default_language", "invoice_prefix", "default_shelf_life_days", "loyalty_points_per_100", "upi_id", "bank_details", "invoice_footer", "road_distance_factor", "default_delivery_fee", "free_delivery_above", "max_delivery_km", "working_days_per_month", "full_day_hours", "half_day_hours"];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Form = Record<string, any>;

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const { t } = useTranslation();
  return <section className="card space-y-4"><div><h2 className="font-semibold">{t(title)}</h2>{hint && <p className="mt-0.5 text-sm text-muted">{t(hint)}</p>}</div>{children}</section>;
}

export default function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const fb = useFeedback();
  const q = useQuery({ queryKey: ["settings"], queryFn: async () => (await api.get("/settings/")).data });
  const [form, setForm] = useState<Form>({});
  const [theme, setTheme] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (q.data) { setForm(q.data); setTheme(q.data.theme ?? {}); } }, [q.data]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      await api.patch("/settings/", { ...Object.fromEntries(KEYS.map((k) => [k, form[k]])), theme });
      applyThemeOverrides(theme);
      qc.invalidateQueries();
      fb.success(t("common:saved"));
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };
  const field = (name: string, label: string, hint?: string, type = "text", textarea = false) => (
    <div className="text-sm"><label className="mb-1 block font-medium" htmlFor={name}>{t(label)}</label>
      {textarea ? <textarea id={name} className="input" rows={3} value={form[name] ?? ""} onChange={(e) => setForm({ ...form, [name]: e.target.value })} />
        : <input id={name} className="input" type={type} inputMode={type === "number" ? "decimal" : undefined} step={type === "number" ? "any" : undefined} value={form[name] ?? ""} onChange={(e) => setForm({ ...form, [name]: e.target.value })} />}
      <Hint text={hint} /></div>
  );
  if (q.isLoading) return <Spinner />;

  return (
    <form onSubmit={save} className="max-w-3xl space-y-5">
      <PageHeader title={t("settings:title")} subtitle={t("hints:page.settingsSub")} />
      <HelpBanner id="settings" text="hints:page.settings" />
      <Section title="settings:business">
        {field("business_name", "settings:businessName")}
        {field("business_address", "common:f.address", undefined, "text", true)}
        <div className="grid gap-4 sm:grid-cols-2">{field("business_phone", "common:f.phone")}{field("business_email", "common:f.email")}</div>
        <div className="grid gap-4 sm:grid-cols-2">{field("default_shelf_life_days", "settings:shelfLife", "hints:settings.shelfLife", "number")}{field("loyalty_points_per_100", "settings:loyalty", "hints:settings.loyalty", "number")}</div>
        <div className="text-sm"><label className="mb-1 block font-medium">{t("settings:defaultLanguage")}</label>
          <select className="input" value={form.default_language ?? "en"} onChange={(e) => setForm({ ...form, default_language: e.target.value })}><option value="en">English</option><option value="ta">தமிழ்</option></select></div>
      </Section>
      <Section title="settings:gst" hint="settings:gstHelp">
        {field("gstin", "common:f.gstin")}
        <div className="text-sm"><label className="mb-1 block font-medium">{t("settings:scheme")}</label>
          <select className="input" value={form.gst_scheme ?? "regular"} onChange={(e) => setForm({ ...form, gst_scheme: e.target.value })}>
            <option value="regular">{t("settings:schemeRegular")}</option><option value="composition">{t("settings:schemeComposition")}</option><option value="unregistered">{t("settings:schemeUnregistered")}</option></select>
          <Hint text="hints:settings.scheme" /></div>
        <label className="flex items-center gap-2 text-sm"><input className="h-5 w-5 accent-[rgb(var(--color-accent))]" type="checkbox" checked={!!form.prices_include_tax} onChange={(e) => setForm({ ...form, prices_include_tax: e.target.checked })} />{t("settings:pricesIncludeTax")}</label>
      </Section>
      <Section title="settings:invoiceSection" hint="hints:settings.invoice">
        {field("invoice_prefix", "settings:invoicePrefix", "hints:settings.prefix")}
        {field("upi_id", "settings:upiId", "hints:settings.upi")}
        {field("bank_details", "settings:bank", "hints:settings.bank", "text", true)}
        {field("invoice_footer", "settings:footer", "hints:settings.footer", "text", true)}
      </Section>
      <Section title="settings:deliverySection" hint="hints:settings.delivery">
        <div className="grid gap-4 sm:grid-cols-2">
          {field("default_delivery_fee", "settings:defaultFee", "hints:settings.defaultFee", "number")}{field("free_delivery_above", "settings:freeAbove", "hints:settings.freeAbove", "number")}
          {field("max_delivery_km", "settings:maxKm", "hints:settings.maxKm", "number")}{field("road_distance_factor", "settings:roadFactor", "hints:settings.roadFactor", "number")}
        </div>
      </Section>
      <Section title="settings:attendanceSection" hint="hints:settings.attendance">
        <div className="grid gap-4 sm:grid-cols-3">
          {field("working_days_per_month", "settings:workingDays", "hints:settings.workingDays", "number")}{field("full_day_hours", "settings:fullDay", "hints:settings.fullDay", "number")}{field("half_day_hours", "settings:halfDay", "hints:settings.halfDay", "number")}
        </div>
      </Section>
      <Section title="settings:theme" hint="settings:themeHelp">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {COLOURS.map((c) => (
            <label key={c} className="text-sm"><span className="mb-1 block font-medium capitalize">{c}</span>
              <input type="color" className="h-11 w-full cursor-pointer rounded-lg border border-border" value={theme[c] ?? DEFAULTS[c]} onChange={(e) => { const next = { ...theme, [c]: e.target.value }; setTheme(next); applyThemeOverrides(next); }} /></label>
          ))}
        </div>
        <button type="button" className="btn-outline" onClick={() => { setTheme({}); applyThemeOverrides({}); }}>{t("settings:resetTheme")}</button>
      </Section>
      {error && <ErrorBox message={error} />}
      <div className="sticky bottom-20 z-10 flex justify-end lg:bottom-4"><button className="btn-primary shadow-lg" disabled={busy}>{busy ? t("common:saving") : t("common:actions.save")}</button></div>
    </form>
  );
}

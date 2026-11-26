import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useFeedback } from "../components/feedback";
import ResourcePage from "../components/ResourcePage";
import { ErrorBox, Spinner } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { money, num } from "../lib/format";
import { payroll } from "./resources";

interface PRow { user: string; employee: string; salary_type: string; days_present: number; credited_days: string; hours: string; incomplete_days: string[]; attendance_pay: string; basis: string; bonus: string; advance: string; deduction: string; net_payable: string; already_generated: boolean }

function Preview() {
  const { t } = useTranslation();
  const fb = useFeedback();
  const qc = useQueryClient();
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const q = useQuery({ queryKey: ["payroll-preview", month], queryFn: async () => (await api.get<{ rows: PRow[] }>("/payroll/preview/", { params: { month } })).data.rows });
  const gen = useMutation({
    mutationFn: async () => (await api.post("/payroll/generate/", { month })).data,
    onSuccess: (d) => { qc.invalidateQueries(); fb.success(t("common:payroll.generated", { count: d.created })); },
    onError: (e) => fb.error(errorMessage(e)),
  });
  const rows = q.data ?? [];
  const pending = rows.some((r) => !r.already_generated && Number(r.attendance_pay) > 0);
  return (
    <div className="card space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="text-sm"><span className="mb-1 block font-medium">{t("common:payroll.month")}</span><input type="month" className="input" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
        <button className="btn-accent" disabled={!pending || gen.isPending} onClick={async () => { if (await fb.confirm({ message: t("common:payroll.confirmGenerate", { month }) })) gen.mutate(); }}>{t("common:payroll.generate")}</button>
      </div>
      {q.isLoading ? <Spinner /> : q.isError ? <ErrorBox message={errorMessage(q.error)} /> : !rows.length ? <p className="text-sm text-muted">{t("common:payroll.noEmployees")}</p> : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.user} className="rounded-xl border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-semibold">{r.employee} {r.already_generated && <span className="ml-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">{t("common:payroll.done")}</span>}</div>
                <div className="text-lg font-bold">{money(r.net_payable)}</div>
              </div>
              <div className="mt-1 text-xs text-muted">{t("common:payroll.basis", { days: r.credited_days, hours: num(r.hours, 2), present: r.days_present })} · {r.basis}</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div><div className="text-[11px] uppercase text-muted">{t("common:payroll.pay")}</div>{money(r.attendance_pay)}</div>
                <div><div className="text-[11px] uppercase text-muted">{t("common:payroll.bonus")}</div>+ {money(r.bonus)}</div>
                <div><div className="text-[11px] uppercase text-muted">{t("common:payroll.advance")}</div>− {money(r.advance)}</div>
                <div><div className="text-[11px] uppercase text-muted">{t("common:payroll.deduction")}</div>− {money(r.deduction)}</div>
              </div>
              {r.incomplete_days.length > 0 && <div className="mt-2 flex items-start gap-2 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{t("common:payroll.incomplete", { days: r.incomplete_days.join(", ") })}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PayrollPage() {
  return <ResourcePage cfg={{ ...payroll, header: <Preview /> }} />;
}

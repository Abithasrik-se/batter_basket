import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import AttendanceWidget from "../components/AttendanceWidget";
import { Empty, HelpBanner, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { dateOnly, dateTime, num } from "../lib/format";

export default function MyAttendance() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["my-attendance"], queryFn: async () => (await api.get("/attendance-check/")).data });
  const recent: { id: string; date: string; check_in: string; check_out: string | null; hours: number | null; source: string }[] = q.data?.recent ?? [];
  return (
    <div className="space-y-4">
      <PageHeader title={t("common:nav.myAttendance")} subtitle={t("hints:page.myAttendanceSub")} />
      <HelpBanner id="my-attendance" text="hints:page.myAttendance" />
      <div className="card flex flex-wrap items-center justify-between gap-3">
        <div><div className="font-semibold">{t("common:attendance.today")}</div><div className="text-sm text-muted">{q.data?.today ? `${dateTime(q.data.today.check_in)}${q.data.today.check_out ? " → " + dateTime(q.data.today.check_out) : ""}` : t("common:attendance.notYet")}</div></div>
        <AttendanceWidget />
      </div>
      <div className="card overflow-hidden p-0">
        {q.isLoading ? <Spinner /> : !recent.length ? <Empty /> : (
          <ul className="divide-y divide-border">
            {recent.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <div><div className="font-medium">{dateOnly(r.date)}</div><div className="text-xs text-muted">{dateTime(r.check_in)}{r.check_out ? ` → ${dateTime(r.check_out)}` : ""}</div></div>
                <div className="text-right">{r.check_out ? <b>{num(r.hours, 2)} h</b> : <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs text-warning">{t("common:attendance.noCheckout")}</span>}{r.source === "manual" && <div className="text-xs text-muted">{t("common:attendance.manual")}</div>}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

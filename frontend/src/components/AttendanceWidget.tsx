import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../lib/api";
import { useFeedback } from "./feedback";

interface Today { state: "none" | "in" | "out"; today: { check_in: string; check_out: string | null; hours: number | null } | null }

/** One-tap daily check in / check out for staff. Payroll is calculated from these records. */
export default function AttendanceWidget({ compact }: { compact?: boolean }) {
  const { t } = useTranslation();
  const fb = useFeedback();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["attendance-today"], queryFn: async () => (await api.get<Today>("/attendance-check/")).data, refetchInterval: 60_000 });
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(i); }, []);
  const m = useMutation({
    mutationFn: async (action: "in" | "out") => (await api.post("/attendance-check/", { action })).data,
    onSuccess: (_d, action) => { qc.invalidateQueries({ queryKey: ["attendance-today"] }); qc.invalidateQueries({ queryKey: ["my-attendance"] }); fb.success(t(action === "in" ? "common:attendance.checkedIn" : "common:attendance.checkedOut")); },
    onError: (e) => fb.error(errorMessage(e)),
  });
  if (!q.data) return null;
  const { state, today } = q.data;
  const mins = today && state === "in" ? Math.max(0, Math.round((now - new Date(today.check_in).getTime()) / 60000)) : 0;
  const elapsed = `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;

  if (state === "out") return <span className="hidden rounded-full bg-success/15 px-3 py-1.5 text-xs font-medium text-success sm:inline">{t("common:attendance.doneToday", { hours: today?.hours ?? 0 })}</span>;
  return state === "none" ? (
    <button className="btn-accent btn-sm" disabled={m.isPending} onClick={() => m.mutate("in")}><LogIn size={15} />{!compact && t("common:attendance.checkIn")}<span className={compact ? "" : "sr-only"}>{compact ? t("common:attendance.checkIn") : ""}</span></button>
  ) : (
    <button className="btn-primary btn-sm" disabled={m.isPending} onClick={() => m.mutate("out")} title={t("common:attendance.working", { elapsed })}><LogOut size={15} />{t("common:attendance.checkOut")} <span className="hidden opacity-70 sm:inline">· {elapsed}</span></button>
  );
}

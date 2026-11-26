import { ChevronDown, HelpCircle, Inbox, X } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export function Spinner() {
  return (
    <div className="space-y-3 p-4" aria-busy="true">
      {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-10" style={{ opacity: 1 - i * 0.18 }} />)}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">{message}</div>;
}

export function Empty({ message, hint }: { message?: string; hint?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <div className="rounded-full bg-secondary p-3 text-muted"><Inbox size={26} /></div>
      <div className="text-sm font-medium">{message ?? t("common:empty")}</div>
      {hint && <div className="max-w-sm text-xs text-muted">{hint}</div>}
    </div>
  );
}

const TONES: Record<string, string> = {
  pending: "warning", confirmed: "info", dispatched: "info", completed: "success", cancelled: "danger",
  paid: "success", unpaid: "danger", partial: "warning", active: "success", inactive: "muted", delivered: "success",
  failed: "danger", assigned: "info", received: "success", draft: "warning", paused: "warning", expired: "muted",
  created: "success", skipped: "muted", sale: "info", purchase: "success", wastage: "danger", damage: "danger", expiry: "warning",
};

export function Badge({ value }: { value: string }) {
  const { t } = useTranslation();
  const tone = TONES[value] ?? "muted";
  const cls: Record<string, string> = {
    warning: "bg-warning/15 text-warning", info: "bg-info/15 text-info", success: "bg-success/15 text-success",
    danger: "bg-danger/15 text-danger", muted: "bg-secondary text-muted",
  };
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls[tone]}`}>{t(`common:status.${value}`, { defaultValue: value })}</span>;
}

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 backdrop-blur-sm sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`flex max-h-[94dvh] w-full flex-col rounded-t-2xl bg-surface shadow-2xl sm:max-h-[90vh] sm:rounded-2xl ${wide ? "sm:max-w-3xl" : "sm:max-w-xl"}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="text-base font-semibold">{title}</h2>
          <button className="btn-ghost btn-sm" aria-label="close" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4" style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}>{children}</div>
      </div>
    </div>
  );
}

export function Pagination({ page, count, pageSize = 25, onPage }: { page: number; count: number; pageSize?: number; onPage: (p: number) => void }) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(count / pageSize));
  return (
    <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-2.5 text-sm text-muted">
      <span>{t("common:pagination.total", { count })}</span>
      <div className="flex items-center gap-2">
        <button className="btn-outline btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="previous">‹</button>
        <span className="tabular-nums">{page} / {pages}</span>
        <button className="btn-outline btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="next">›</button>
      </div>
    </div>
  );
}

/** Small muted guidance text under a form field. */
export function Hint({ text }: { text?: string }) {
  const { t } = useTranslation();
  return text ? <span className="mt-1 block text-xs leading-snug text-muted">{t(text)}</span> : null;
}

/** Page-level "how this works" panel. Open the first time, then remembers if you closed it. */
export function HelpBanner({ id, text }: { id: string; text: string }) {
  const { t } = useTranslation();
  const key = `zeal.help.${id}`;
  const [open, setOpen] = useState(() => localStorage.getItem(key) !== "closed");
  const toggle = () => { const n = !open; setOpen(n); localStorage.setItem(key, n ? "open" : "closed"); };
  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5">
      <button type="button" onClick={toggle} className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium" aria-expanded={open}>
        <HelpCircle size={16} className="text-accent" /><span className="flex-1">{t("common:help.title")}</span>
        <ChevronDown size={16} className={`text-muted transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="whitespace-pre-line px-4 pb-3 text-sm leading-relaxed text-muted">{t(text)}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-semibold sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        <div className="gold-line mt-2 w-24" />
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

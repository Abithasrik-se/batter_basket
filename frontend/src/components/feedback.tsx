import { CheckCircle2, Info, XCircle } from "lucide-react";
import { createContext, ReactNode, useCallback, useContext, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; text: string }
interface ConfirmOpts { title?: string; message: string; danger?: boolean; confirmLabel?: string }

interface Ctx {
  success: (t: string) => void;
  error: (t: string) => void;
  info: (t: string) => void;
  confirm: (o: ConfirmOpts) => Promise<boolean>;
}
const FeedbackCtx = createContext<Ctx>(null as unknown as Ctx);
export const useFeedback = () => useContext(FeedbackCtx);

/** Toast notifications and a styled confirm dialog (replaces window.alert / window.confirm). */
export function FeedbackProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dialog, setDialog] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const seq = useRef(0);

  const push = useCallback((kind: Kind, text: string) => {
    const id = ++seq.current;
    setToasts((l) => [...l, { id, kind, text }]);
    setTimeout(() => setToasts((l) => l.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);

  const value = useMemo<Ctx>(() => ({
    success: (x) => push("success", x), error: (x) => push("error", x), info: (x) => push("info", x),
    confirm: (o) => new Promise<boolean>((resolve) => setDialog({ ...o, resolve })),
  }), [push]);

  const close = (v: boolean) => { dialog?.resolve(v); setDialog(null); };
  const icon = { success: <CheckCircle2 size={18} className="text-success" />, error: <XCircle size={18} className="text-danger" />, info: <Info size={18} className="text-info" /> };

  return (
    <FeedbackCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[70] flex flex-col items-center gap-2 px-3 sm:bottom-6 sm:items-end sm:px-6" aria-live="polite">
        {toasts.map((x) => (
          <div key={x.id} role="status" className="pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm shadow-xl">
            <span className="mt-0.5">{icon[x.kind]}</span><span className="flex-1 break-words">{x.text}</span>
          </div>
        ))}
      </div>
      {dialog && (
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/55 p-3 backdrop-blur-sm sm:items-center" onClick={() => close(false)}>
          <div role="alertdialog" aria-modal="true" className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-1 text-base font-semibold">{dialog.title ?? t("common:confirm.title")}</h2>
            <p className="mb-5 text-sm text-muted">{dialog.message}</p>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => close(false)}>{t("common:actions.cancel")}</button>
              <button className={dialog.danger ? "btn-danger" : "btn-primary"} onClick={() => close(true)}>{dialog.confirmLabel ?? t("common:confirm.yes")}</button>
            </div>
          </div>
        </div>
      )}
    </FeedbackCtx.Provider>
  );
}

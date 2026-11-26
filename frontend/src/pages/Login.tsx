import { Eye, EyeOff } from "lucide-react";
import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import LanguageSwitch from "../components/LanguageSwitch";
import { ErrorBox } from "../components/ui";
import { errorMessage } from "../lib/api";

export default function Login() {
  const { t } = useTranslation();
  const { me, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (me) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await login(username, password); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-[#0b0b0b] p-4">
      <div className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-accent/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-accent/15 blur-3xl" />
      <div className="relative w-full max-w-sm">
        <div className="mb-4 flex justify-end"><div className="rounded-lg bg-surface/95"><LanguageSwitch /></div></div>
        <div className="rounded-2xl bg-surface p-6 shadow-2xl sm:p-8">
          <img src="/logo-mark.png" alt="Zeal" className="mx-auto mb-3 h-24 w-auto" />
          <h1 className="text-center text-xl font-bold">{t("common:app.name")}</h1>
          <p className="mb-6 mt-1 text-center text-sm text-muted">{t("common:auth.subtitle")}</p>
          <form onSubmit={submit} className="space-y-4">
            <div><label className="mb-1 block text-sm font-medium" htmlFor="u">{t("common:auth.username")}</label>
              <input id="u" className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" required /></div>
            <div><label className="mb-1 block text-sm font-medium" htmlFor="p">{t("common:auth.password")}</label>
              <div className="relative"><input id="p" className="input pr-11" type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
                <button type="button" className="absolute right-1 top-1/2 -translate-y-1/2 p-2 text-muted" aria-label={t("common:auth.togglePassword")} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></div>
            {error && <ErrorBox message={error} />}
            <button className="btn-accent w-full" disabled={busy}>{busy ? t("common:saving") : t("common:auth.signIn")}</button>
          </form>
          <p className="mt-4 text-center text-xs text-muted">{t("hints:page.loginHelp")}</p>
        </div>
      </div>
    </div>
  );
}

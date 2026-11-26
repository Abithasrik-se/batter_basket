import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";

/** [ English | தமிழ் ] toggle, used on the login page and the top bar. */
export default function LanguageSwitch() {
  const { i18n } = useTranslation();
  const { setLanguage } = useAuth();
  const item = (code: "en" | "ta", label: string) => (
    <button
      onClick={() => setLanguage(code)}
      aria-pressed={i18n.language === code}
      className={`px-3 py-1 text-sm ${i18n.language === code ? "bg-primary text-primary-foreground" : "bg-surface text-text hover:bg-secondary"}`}
    >{label}</button>
  );
  return (
    <div className="inline-flex overflow-hidden rounded border border-border" role="group" aria-label="Language">
      {item("en", "English")}{item("ta", "தமிழ்")}
    </div>
  );
}

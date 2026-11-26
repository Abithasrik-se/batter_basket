import i18n from "../i18n";

const locale = () => (i18n.language === "ta" ? "ta-IN" : "en-IN");

export const money = (v: string | number | null | undefined) =>
  new Intl.NumberFormat(locale(), { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(v ?? 0));

export const num = (v: string | number | null | undefined, digits = 3) =>
  new Intl.NumberFormat(locale(), { maximumFractionDigits: digits }).format(Number(v ?? 0));

export const dateOnly = (v?: string | null) => (v ? new Intl.DateTimeFormat(locale(), { dateStyle: "medium" }).format(new Date(v)) : "");

export const dateTime = (v?: string | null) =>
  v ? new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(new Date(v)) : "";

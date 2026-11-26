import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Every locales/<lang>/<namespace>.json file is picked up automatically.
const files = import.meta.glob("./locales/*/*.json", { eager: true }) as Record<string, { default: Record<string, unknown> }>;
const resources: Record<string, Record<string, Record<string, unknown>>> = {};
for (const [path, mod] of Object.entries(files)) {
  const [, lang, ns] = /\.\/locales\/(\w+)\/(\w+)\.json$/.exec(path)!;
  (resources[lang] ??= {})[ns] = mod.default;
}

export const LANG_KEY = "zeal.lang";
const saved = localStorage.getItem(LANG_KEY);

i18n.use(initReactI18next).init({
  resources,
  lng: saved === "ta" ? "ta" : "en",
  fallbackLng: "en",
  defaultNS: "common",
  ns: Object.keys(resources.en),
  interpolation: { escapeValue: false },
  // In development a missing key is reported loudly so it is never forgotten
  saveMissing: import.meta.env.DEV,
  missingKeyHandler: (_lngs, ns, key) => console.warn(`[i18n] missing key ${ns}:${key}`),
});

document.documentElement.lang = i18n.language;
i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  localStorage.setItem(LANG_KEY, lng);
});

export default i18n;

// Fails (exit 1) when
//  1. a key exists in English but not in Tamil (or the reverse), or
//  2. code uses a key like t("orders:f.number") that does not exist in English.
// Run: npm run i18n:check   (also runs in CI)
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../src");
const flat = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) => (typeof v === "object" && v ? flat(v, `${prefix}${k}.`) : [`${prefix}${k}`]));

const langs = ["en", "ta"];
const keys = {};
for (const lang of langs) {
  const dir = path.join(root, "i18n/locales", lang);
  for (const f of fs.readdirSync(dir).filter((f) => f.endsWith(".json"))) {
    const ns = f.replace(".json", "");
    (keys[lang] ??= new Set());
    flat(JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"))).forEach((k) => keys[lang].add(`${ns}:${k}`));
  }
}
let bad = 0;
for (const [a, b] of [["en", "ta"], ["ta", "en"]])
  for (const k of keys[a]) if (!keys[b].has(k)) { console.error(`Missing in ${b}: ${k}`); bad++; }

const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
const used = new Set();
for (const file of walk(root).filter((f) => /\.(tsx?|jsx?)$/.test(f)))
  for (const m of fs.readFileSync(file, "utf8").matchAll(/["'`]([a-z]+:[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)["'`]/g)) used.add(m[1]);
const namespaces = new Set([...keys.en].map((k) => k.split(":")[0]));
for (const k of used)
  if (namespaces.has(k.split(":")[0]) && !keys.en.has(k)) { console.error(`Used in code but not defined: ${k}`); bad++; }

console.log(bad ? `i18n check FAILED (${bad} problems)` : `i18n check OK (${keys.en.size} keys, en/ta in sync)`);
process.exit(bad ? 1 : 0);

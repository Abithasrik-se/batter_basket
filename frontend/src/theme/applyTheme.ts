// Applies brand overrides stored by the owner (Settings -> theme) on top of theme.css.
// theme JSON looks like: { "primary": "#0B0B0B", "accent": "#C9971C" }
const TOKENS = ["primary", "primary-foreground", "secondary", "accent", "accent-foreground", "background", "surface", "border", "text", "muted", "success", "warning", "danger", "info"];

function hexToTriple(hex: string): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

export function applyThemeOverrides(theme: Record<string, string> | undefined | null) {
  const root = document.documentElement;
  TOKENS.forEach((t) => root.style.removeProperty(`--color-${t}`));
  if (!theme) return;
  for (const [key, value] of Object.entries(theme)) {
    const triple = hexToTriple(value);
    if (triple && TOKENS.includes(key)) root.style.setProperty(`--color-${key}`, triple);
  }
}

export function setMode(mode: "light" | "dark") {
  document.documentElement.dataset.theme = mode;
  localStorage.setItem("zeal.mode", mode);
}

export function initMode() {
  setMode((localStorage.getItem("zeal.mode") as "light" | "dark") || "light");
}

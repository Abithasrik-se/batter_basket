# Bilingual (English + தமிழ்) and branding

## Translations
- Files: `frontend/src/i18n/locales/en/<ns>.json` and `ta/<ns>.json` (namespaces: common, dashboard, inventory, production, orders, masters, delivery, settings, hints). Every file is loaded automatically.
- Use keys, never text: `t("orders:f.number")` = namespace `orders`, key `f.number`. Always write the namespace prefix; the checker relies on it.
- **Add a translation:** add the key to the `en` file and the same key to `ta`, use it in code, run `npm run i18n:check`.
- **Prevent missing translations:** `npm run i18n:check` fails if a key exists in one language only, or if code uses an undefined key. In development the browser console also warns `[i18n] missing key`. Add it to CI (already in `.github/workflows/ci.yml`).
- Switcher `[ English | தமிழ் ]` is on the login page and top bar. No reload. Saved in `localStorage` (guests) and in the user's profile (`preferred_language`).
- Numbers, ₹ and dates use `Intl` with the `en-IN` / `ta-IN` locale (`lib/format.ts`). Fonts: Inter + Noto Sans Tamil (self-hosted).
- **Not translated on purpose:** customer names, addresses, notes, batch numbers. Products and raw materials have an optional Tamil name field.
- Have a Tamil-speaking staff member review wording; the supplied Tamil is a first draft.

## Branding
- All colours live in `frontend/src/theme/theme.css` as CSS variables. Tailwind only knows names like `bg-primary`, `text-muted`, `border-border` (`tailwind.config.js`). No component contains a hex code.
- **Rebrand:** edit the values in `theme.css` (e.g. `--color-accent: 201 151 28`). Values are `R G B` so opacity utilities work.
- **Admin-controlled theme (already included):** Settings → Brand colours saves `{primary, accent, background, surface, text}` into `SystemSettings.theme`; `applyTheme.ts` writes them onto `:root` at load for everyone. "Reset colours" returns to `theme.css`.
- The logo colours in `theme.css` are approximate; sample exact values from your logo file. Gold on white has low contrast for small text, so gold is used for accents and buttons, black for text.
- Dark mode: toggle in the top bar (`[data-theme="dark"]` block in `theme.css`).

## Hints
Guidance texts live in the `hints` namespace: `hints:page.<screen>` is the 'How this page works' panel (opens the first time, remembers if you close it), `hints:field.<name>` is the small text under a form field, `hints:dash.*` are dashboard card tips. Add a hint to a form field with `hint: "hints:field.xxx"` in `pages/resources.tsx`.

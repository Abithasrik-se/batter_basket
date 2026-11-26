/** Tailwind only knows SEMANTIC names (primary, accent, surface...). The real colours live in
 *  src/theme/theme.css, so rebranding never touches a component. */
const token = (name) => `rgb(var(--color-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
        secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
        accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
        background: token("background"),
        surface: token("surface"),
        border: token("border"),
        text: token("text"),
        muted: token("muted"),
        success: token("success"),
        warning: token("warning"),
        danger: token("danger"),
        info: token("info"),
      },
      fontFamily: { sans: "var(--font-sans)" },
      borderRadius: { DEFAULT: "var(--radius)", lg: "calc(var(--radius) + 4px)" },
    },
  },
  plugins: [],
};

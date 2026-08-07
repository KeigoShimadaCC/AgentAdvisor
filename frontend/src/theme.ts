import { safeStorage } from "./lib/safeStorage";
/**
 * The theme control (SPEC-045's mechanism, SPEC-052's control).
 *
 * `styles/tokens.css` has carried `:root[data-theme="dark"]` and
 * `:root[data-theme="light"]` blocks since SPEC-045, written so an explicit
 * choice beats the OS media query in *both* directions — light under a dark OS
 * preference, and dark under a light one. Nothing ever set the attribute, so
 * every user got their OS preference and no say in it.
 *
 * Three choices, not two: "match my system" is a real preference and the
 * default, and collapsing it into light-or-dark would force a decision on
 * people who do not have one.
 */
export type ThemeChoice = "system" | "light" | "dark";

export const THEMES: { key: ThemeChoice; label: string; blurb: string }[] = [
  { key: "system", label: "Match my system", blurb: "Follow the light or dark setting on this device." },
  { key: "light", label: "Light", blurb: "Always light, whatever the device says." },
  { key: "dark", label: "Dark", blurb: "Always dark, whatever the device says." },
];

const STORAGE_KEY = "agentadvisor:theme";
const DEFAULT_THEME: ThemeChoice = "system";

function isTheme(value: unknown): value is ThemeChoice {
  return value === "system" || value === "light" || value === "dark";
}

export function readTheme(): ThemeChoice {
  const raw = safeStorage.get(STORAGE_KEY);
  return isTheme(raw) ? raw : DEFAULT_THEME;
}

/** Stamp the root element. `system` removes the attribute so the media query wins. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

export function writeTheme(choice: ThemeChoice): void {
  safeStorage.set(STORAGE_KEY, choice);
  applyTheme(choice);
}

/** Called once at startup, before first paint, so there is no theme flash. */
export function initTheme(): void {
  applyTheme(readTheme());
}

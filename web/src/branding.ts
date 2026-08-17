import { getPresetColors, type BrandingColorKeys, type ColorModeKey } from "./brandingPresets";

export type Branding = {
  product_name: string;
  tagline: string;
  logo_src: string;
  favicon_src: string;
  preset_id: string;
  color_mode: string;
  colors: Record<string, string>;
  /** Optional field overrides echoed by API (null/undefined = use preset). */
  primary?: string | null;
  primary_soft?: string | null;
  bg?: string | null;
  surface?: string | null;
  text?: string | null;
  muted?: string | null;
};

export const DEFAULT_BRANDING: Branding = {
  product_name: "元景.智数",
  tagline: "运营商智能问数",
  logo_src: "/logo.svg",
  favicon_src: "/logo.svg",
  preset_id: "default",
  color_mode: "light",
  colors: {},
};

const COLOR_KEYS: BrandingColorKeys[] = [
  "primary",
  "primary_soft",
  "bg",
  "surface",
  "text",
  "muted",
];

const VAR_MAP: Record<BrandingColorKeys, string> = {
  primary: "--accent",
  primary_soft: "--accent-soft",
  bg: "--bg",
  surface: "--surface",
  text: "--text",
  muted: "--muted",
};

const INLINE_VARS = [...Object.values(VAR_MAP), "--accent-ink", "--ink"] as const;

let lastBranding: Branding | null = null;
let systemMedia: MediaQueryList | null = null;
let systemListener: ((ev: MediaQueryListEvent) => void) | null = null;

/**
 * Resolve branding asset URLs for the browser.
 * `/logo.svg` stays same-origin; `/media/...` is rewritten through the API base
 * (`/api` by default) so vite/nginx proxy reaches FastAPI media routes.
 */
export function resolvePublicAssetUrl(src: string): string {
  if (!src) return "/logo.svg";
  if (/^(https?:|data:|blob:)/i.test(src)) return src;
  if (src.startsWith("/media/")) {
    const envBase = import.meta.env.VITE_API_BASE as string | undefined;
    const base = (envBase || "/api").replace(/\/$/, "");
    return `${base}${src}`;
  }
  return src.startsWith("/") ? src : `/${src}`;
}

/** Alias — same-origin `/media` via API proxy (see resolvePublicAssetUrl). */
export const resolveMediaUrl = resolvePublicAssetUrl;

export function resolveEffectiveMode(colorMode: string): ColorModeKey {
  if (colorMode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return colorMode === "dark" ? "dark" : "light";
}

function overrideValue(b: Branding, key: BrandingColorKeys): string | undefined {
  const direct = b[key];
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  return undefined;
}

/** Resolve effective palette for the given branding + resolved light/dark mode. */
export function resolveBrandingColors(
  b: Branding,
  mode: ColorModeKey,
): Record<BrandingColorKeys, string> {
  // Prefer client presets so system→dark does not inherit light-base `b.colors`.
  const resolved = getPresetColors(b.preset_id || "default", mode);

  for (const key of COLOR_KEYS) {
    const ov = overrideValue(b, key);
    if (ov) {
      resolved[key] = ov;
    }
  }

  return resolved;
}

function clearInlineThemeVars(root: HTMLElement) {
  for (const cssVar of INLINE_VARS) {
    root.style.removeProperty(cssVar);
  }
}

function syncSystemListener(colorMode: string) {
  if (colorMode !== "system") {
    if (systemMedia && systemListener) {
      systemMedia.removeEventListener("change", systemListener);
    }
    systemMedia = null;
    systemListener = null;
    return;
  }
  if (systemListener) return;
  systemMedia = window.matchMedia("(prefers-color-scheme: dark)");
  systemListener = () => {
    if (lastBranding && lastBranding.color_mode === "system") {
      applyBranding(lastBranding);
    }
  };
  systemMedia.addEventListener("change", systemListener);
}

export function applyBranding(b: Branding) {
  lastBranding = b;
  const root = document.documentElement;
  const mode = resolveEffectiveMode(b.color_mode);
  root.dataset.theme = mode;

  clearInlineThemeVars(root);

  const colors = resolveBrandingColors(b, mode);
  for (const key of COLOR_KEYS) {
    const cssVar = VAR_MAP[key];
    if (colors[key]) root.style.setProperty(cssVar, colors[key]);
  }
  if (colors.primary) {
    root.style.setProperty("--accent-ink", colors.primary);
  }
  if (colors.text) {
    root.style.setProperty("--ink", colors.text);
  }

  let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (link) link.href = resolvePublicAssetUrl(b.favicon_src || "/logo.svg");

  syncSystemListener(b.color_mode);
}

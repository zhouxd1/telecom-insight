export type Branding = {
  product_name: string;
  tagline: string;
  logo_src: string;
  favicon_src: string;
  preset_id: string;
  color_mode: string;
  colors: Record<string, string>;
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

const VAR_MAP: Record<string, string> = {
  primary: "--accent",
  primary_soft: "--accent-soft",
  bg: "--bg",
  surface: "--surface",
  text: "--text",
  muted: "--muted",
};

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

export function applyBranding(b: Branding) {
  const root = document.documentElement;
  const mode =
    b.color_mode === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : b.color_mode;
  root.dataset.theme = mode;
  for (const [k, cssVar] of Object.entries(VAR_MAP)) {
    if (b.colors[k]) root.style.setProperty(cssVar, b.colors[k]);
  }
  if (b.colors.primary) {
    root.style.setProperty("--accent-ink", b.colors.primary);
  }
  let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (link) link.href = resolvePublicAssetUrl(b.favicon_src || "/logo.svg");
}

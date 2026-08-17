"""Built-in branding color presets (light / dark baselines)."""

from __future__ import annotations

# Flat 2.0 teal tokens from web/src/styles.css (:root --accent, --bg, etc.)
_DEFAULT_LIGHT = {
    "primary": "#0d9488",
    "primary_soft": "#ecfdf8",
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "text": "#2c313a",
    "muted": "#6b7280",
}

_DEFAULT_DARK = {
    "primary": "#2dd4bf",
    "primary_soft": "#134e4a",
    "bg": "#0f1419",
    "surface": "#1a1f26",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
}

PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "default": {
        "light": dict(_DEFAULT_LIGHT),
        "dark": dict(_DEFAULT_DARK),
    },
    "ocean": {
        "light": {
            "primary": "#2563eb",
            "primary_soft": "#eff6ff",
            "bg": "#f5f7fb",
            "surface": "#ffffff",
            "text": "#1e293b",
            "muted": "#64748b",
        },
        "dark": {
            "primary": "#60a5fa",
            "primary_soft": "#1e3a5f",
            "bg": "#0b1220",
            "surface": "#152033",
            "text": "#e2e8f0",
            "muted": "#94a3b8",
        },
    },
    "slate": {
        "light": {
            "primary": "#475569",
            "primary_soft": "#f1f5f9",
            "bg": "#f8fafc",
            "surface": "#ffffff",
            "text": "#0f172a",
            "muted": "#64748b",
        },
        "dark": {
            "primary": "#94a3b8",
            "primary_soft": "#334155",
            "bg": "#0f172a",
            "surface": "#1e293b",
            "text": "#f1f5f9",
            "muted": "#94a3b8",
        },
    },
    "amber": {
        "light": {
            "primary": "#d97706",
            "primary_soft": "#fffbeb",
            "bg": "#faf8f5",
            "surface": "#ffffff",
            "text": "#1c1917",
            "muted": "#78716c",
        },
        "dark": {
            "primary": "#fbbf24",
            "primary_soft": "#78350f",
            "bg": "#1c1917",
            "surface": "#292524",
            "text": "#fafaf9",
            "muted": "#a8a29e",
        },
    },
}

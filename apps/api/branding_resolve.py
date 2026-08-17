"""Resolve org branding colors from preset + optional overrides."""

from __future__ import annotations

from apps.api.branding_presets import PRESETS


def resolve_branding_colors(*, preset_id: str, color_mode: str, overrides: dict) -> dict[str, str]:
    mode = "dark" if color_mode == "dark" else "light"
    # system resolved on client; server returns light base + mode flag
    base = PRESETS.get(preset_id, PRESETS["default"])[mode]
    out = dict(base)
    for k in ("primary", "primary_soft", "bg", "surface", "text", "muted"):
        v = overrides.get(k)
        if v:
            out[k] = v
    return out

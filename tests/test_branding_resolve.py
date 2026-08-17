from apps.api.branding_resolve import resolve_branding_colors
from apps.api.branding_presets import PRESETS


def test_default_preset_has_primary():
    assert "default" in PRESETS
    colors = resolve_branding_colors(preset_id="default", color_mode="light", overrides={})
    assert colors["primary"].startswith("#")


def test_override_primary_wins():
    colors = resolve_branding_colors(
        preset_id="default", color_mode="light", overrides={"primary": "#112233"}
    )
    assert colors["primary"] == "#112233"

"""Org branding read/update APIs (upload/media in a later task)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.branding_presets import PRESETS
from apps.api.branding_resolve import resolve_branding_colors
from apps.api.db import get_session
from apps.api.deps import get_current_user, require_org_admin
from apps.api.models_db import TiOrg, TiOrgBranding, TiUser
from apps.api.schemas import BrandingOut, BrandingUpdate

router = APIRouter(tags=["branding"])

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COLOR_FIELDS = ("primary", "primary_soft", "bg", "surface", "text", "muted")
_COLOR_MODES = frozenset({"light", "dark", "system"})

_DEFAULT_PRODUCT_NAME = "元景.智数"
_DEFAULT_TAGLINE = "运营商智能问数"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _media_src(org_id: int | None, relative_path: str | None, fallback_url: str | None, default: str) -> str:
    if relative_path and org_id is not None:
        filename = Path(relative_path).name
        return f"/media/branding/{org_id}/{filename}"
    if fallback_url:
        return fallback_url
    return default


def branding_out(row: TiOrgBranding | None, *, org_id: int | None = None) -> BrandingOut:
    if row is None:
        oid = org_id
        product_name = _DEFAULT_PRODUCT_NAME
        tagline = _DEFAULT_TAGLINE
        logo_url = None
        logo_path = None
        favicon_url = None
        favicon_path = None
        preset_id = "default"
        color_mode = "light"
        overrides: dict[str, str | None] = {k: None for k in _COLOR_FIELDS}
    else:
        oid = row.org_id
        product_name = row.product_name
        tagline = row.tagline
        logo_url = row.logo_url
        logo_path = row.logo_path
        favicon_url = row.favicon_url
        favicon_path = row.favicon_path
        preset_id = row.preset_id
        color_mode = row.color_mode
        overrides = {k: getattr(row, k) for k in _COLOR_FIELDS}

    colors = resolve_branding_colors(
        preset_id=preset_id,
        color_mode=color_mode,
        overrides={k: v for k, v in overrides.items() if v},
    )
    return BrandingOut(
        org_id=oid,
        product_name=product_name,
        tagline=tagline,
        logo_url=logo_url,
        logo_path=logo_path,
        logo_src=_media_src(oid, logo_path, logo_url, "/logo.svg"),
        favicon_url=favicon_url,
        favicon_path=favicon_path,
        favicon_src=_media_src(oid, favicon_path, favicon_url, "/logo.svg"),
        preset_id=preset_id,
        color_mode=color_mode,
        primary=overrides.get("primary"),
        primary_soft=overrides.get("primary_soft"),
        bg=overrides.get("bg"),
        surface=overrides.get("surface"),
        text=overrides.get("text"),
        muted=overrides.get("muted"),
        colors=colors,
    )


def _get_or_create_branding(session: Session, org_id: int) -> TiOrgBranding:
    row = session.get(TiOrgBranding, org_id)
    if row is not None:
        return row
    row = TiOrgBranding(
        org_id=org_id,
        product_name=_DEFAULT_PRODUCT_NAME,
        tagline=_DEFAULT_TAGLINE,
        preset_id="default",
        color_mode="light",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _validate_update(body: BrandingUpdate) -> None:
    data = body.model_dump(exclude_unset=True)
    for key in ("product_name", "tagline", "preset_id", "color_mode"):
        if key in data and data[key] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{key} cannot be null",
            )
    if "preset_id" in data and data["preset_id"] is not None:
        if data["preset_id"] not in PRESETS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid preset_id",
            )
    if "color_mode" in data and data["color_mode"] is not None:
        if data["color_mode"] not in _COLOR_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid color_mode",
            )
    for key in _COLOR_FIELDS:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            continue
        if not _HEX_RE.match(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid {key}: expected #RRGGBB",
            )


@router.get("/branding/default", response_model=BrandingOut)
def get_default_branding(session: Session = Depends(get_session)):
    org = session.exec(select(TiOrg).order_by(TiOrg.id)).first()
    if org is None or org.id is None:
        return branding_out(None)
    row = session.get(TiOrgBranding, org.id)
    return branding_out(row, org_id=org.id)


@router.get("/orgs/me/branding", response_model=BrandingOut)
def get_my_branding(
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    row = _get_or_create_branding(session, user.org_id)
    return branding_out(row)


@router.put("/orgs/me/branding", response_model=BrandingOut)
def update_my_branding(
    body: BrandingUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _validate_update(body)
    row = _get_or_create_branding(session, user.org_id)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return branding_out(row)

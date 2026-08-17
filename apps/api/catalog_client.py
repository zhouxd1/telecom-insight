"""HTTP client for the Catalog service (schema introspect + grants)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from apps.api.settings import settings

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _base() -> str:
    return settings.catalog_base_url.rstrip("/")


def _raise_unavailable(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="catalog service unavailable",
    ) from exc


def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{_base()}{path}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        _raise_unavailable(exc)
    if resp.status_code >= 400:
        detail: Any
        try:
            detail = resp.json()
        except Exception:  # noqa: BLE001
            detail = resp.text or f"catalog error {resp.status_code}"
        raise HTTPException(status_code=resp.status_code, detail=detail)
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def introspect(
    *,
    workspace_id: int,
    datasource_id: int,
    db_type: str,
    sqlalchemy_url: str,
) -> dict[str, Any]:
    return _request(
        "POST",
        "/v1/introspect",
        json={
            "workspace_id": workspace_id,
            "datasource_id": datasource_id,
            "db_type": db_type,
            "sqlalchemy_url": sqlalchemy_url,
        },
    )


def get_schema(*, workspace_id: int, datasource_id: int) -> dict[str, Any]:
    return _request(
        "GET",
        f"/v1/workspaces/{workspace_id}/schema",
        params={"datasource_id": datasource_id},
    )


def put_grants(
    *,
    workspace_id: int,
    datasource_id: int,
    tables: list[dict[str, Any]],
) -> dict[str, Any]:
    return _request(
        "PUT",
        f"/v1/workspaces/{workspace_id}/grants",
        json={"datasource_id": datasource_id, "tables": tables},
    )


def get_effective(*, workspace_id: int, datasource_id: int) -> dict[str, Any]:
    return _request(
        "GET",
        f"/v1/workspaces/{workspace_id}/effective",
        params={"datasource_id": datasource_id},
    )

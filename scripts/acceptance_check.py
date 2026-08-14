#!/usr/bin/env python3
"""Smoke / acceptance checks for 元景.智数 API.

Requires a running API by default (docker compose). Exits non-zero on failure.

  python scripts/acceptance_check.py
  TI_API_BASE=http://localhost:8000 TI_RUN_ASK=1 python scripts/acceptance_check.py

Set TI_USE_TESTCLIENT=1 to run the same checks via FastAPI TestClient (no server).
"""

from __future__ import annotations

import os
import sys
from typing import Any

DOMAINS = ("biz", "network", "cs")
MIN_RECOMMENDED = 8


def _base_url() -> str:
    return os.environ.get("TI_API_BASE", "http://localhost:8000").rstrip("/")


def _run_ask() -> bool:
    return os.environ.get("TI_RUN_ASK", "").strip() in {"1", "true", "True", "yes"}


def _use_testclient() -> bool:
    return os.environ.get("TI_USE_TESTCLIENT", "").strip() in {"1", "true", "True", "yes"}


class _HttpClient:
    """Thin wrapper: live httpx or in-process TestClient."""

    def __init__(self, client: Any, *, label: str):
        self._c = client
        self.label = label

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._c.get(path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._c.post(path, **kwargs)

    def close(self) -> None:
        close = getattr(self._c, "close", None)
        if callable(close):
            close()


def _make_client() -> _HttpClient:
    if _use_testclient():
        from fastapi.testclient import TestClient

        from apps.api.main import app

        return _HttpClient(TestClient(app), label="TestClient")

    import httpx

    base = _base_url()
    return _HttpClient(httpx.Client(base_url=base, timeout=30.0), label=base)


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def main() -> int:
    client = _make_client()
    print(f"acceptance_check against {client.label}")
    try:
        r = client.get("/health")
        if r.status_code != 200:
            _fail(f"/health status {r.status_code}")
        body = r.json()
        if body.get("status") != "ok":
            _fail(f"/health body {body}")
        _ok("/health")

        user = os.environ.get("TI_DEMO_USERNAME", "demo")
        password = os.environ.get("TI_DEMO_PASSWORD", "demo123")
        r = client.post("/auth/login", json={"username": user, "password": password})
        if r.status_code != 200:
            _fail(f"login status {r.status_code}: {r.text}")
        token = r.json().get("access_token")
        if not token:
            _fail("login missing access_token")
        headers = {"Authorization": f"Bearer {token}"}
        _ok("login")

        r = client.get("/domains", headers=headers)
        if r.status_code != 200:
            _fail(f"/domains status {r.status_code}")
        ids = {d["id"] for d in r.json()}
        missing = set(DOMAINS) - ids
        if missing:
            _fail(f"/domains missing {sorted(missing)}")
        _ok(f"/domains {sorted(ids)}")

        for domain in DOMAINS:
            r = client.get(f"/domains/{domain}/recommended", headers=headers)
            if r.status_code != 200:
                _fail(f"recommended/{domain} status {r.status_code}")
            items = r.json()
            if not isinstance(items, list) or len(items) < MIN_RECOMMENDED:
                _fail(
                    f"recommended/{domain} expected >= {MIN_RECOMMENDED}, got {len(items) if isinstance(items, list) else type(items)}"
                )
            _ok(f"recommended/{domain} count={len(items)}")

            if _run_ask():
                text = items[0].get("text") if items else None
                if not text:
                    _fail(f"ask/{domain}: empty recommended text")
                r = client.post(
                    "/ask",
                    headers=headers,
                    json={"domain": domain, "question": text},
                )
                if r.status_code != 200:
                    _fail(f"ask/{domain} HTTP {r.status_code}: {r.text}")
                ask_body = r.json()
                status = ask_body.get("status")
                if status not in {"ok", "clarify", "error"}:
                    _fail(f"ask/{domain} unexpected status {status}")
                if status == "ok":
                    for key in ("rows", "chart", "narrative"):
                        if key not in ask_body:
                            _fail(f"ask/{domain} missing key {key}")
                _ok(f"ask/{domain} status={status}")

        print("ALL CHECKS PASSED")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — top-level CLI
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

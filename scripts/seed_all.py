#!/usr/bin/env python3
"""Seed Postgres warehouse from packs/*/seed/*.sql."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = Path(os.environ.get("TI_PACKS_ROOT", ROOT / "packs"))
DATABASE_URL = os.environ.get(
    "TI_DATABASE_URL",
    "postgresql+psycopg://postgres:telecom@localhost:5432/telecom",
)
DOMAINS = ("biz", "network", "cs")


def _statements(sql: str) -> list[str]:
    """Split a seed file into executable SQL statements."""
    out: list[str] = []
    for chunk in sql.split(";"):
        lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if lines:
            out.append("\n".join(lines))
    return out


def main() -> int:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for domain in DOMAINS:
            seed_dir = PACKS_ROOT / domain / "seed"
            if not seed_dir.is_dir():
                print(f"skip {domain}: no seed directory at {seed_dir}")
                continue
            for sql_path in sorted(seed_dir.glob("*.sql")):
                for stmt in _statements(sql_path.read_text(encoding="utf-8")):
                    conn.execute(text(stmt))
                print(f"ok {domain}/{sql_path.name}")
    print("seed complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

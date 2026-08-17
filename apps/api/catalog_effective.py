"""Helpers to turn Catalog effective grants into AskEngine kwargs."""

from __future__ import annotations

from typing import Any


def parse_effective_grants(
    effective: dict[str, Any],
) -> tuple[set[str], dict[str, set[str]]]:
    """Convert Catalog effective JSON into table whitelist + column allow map."""
    tables = {str(t) for t in (effective.get("tables") or [])}
    columns_raw = effective.get("columns") or {}
    allowed_columns: dict[str, set[str]] = {
        str(table): {str(c) for c in (cols or [])}
        for table, cols in columns_raw.items()
    }
    return tables, allowed_columns

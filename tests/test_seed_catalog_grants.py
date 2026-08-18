"""Demo Catalog grant seed must not overwrite existing workspace grants."""

from __future__ import annotations

import pytest

from apps.api import catalog_client, db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.seed_catalog import seed_demo_catalog_grants
from apps.api.settings import settings


@pytest.fixture
def seeded_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "seed_cat.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    yield engine
    db.reset_engine()


def test_seed_skips_put_when_grants_already_exist(seeded_engine, monkeypatch):
    put_calls: list[dict] = []

    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {
            "tables": ["sub_month"],
            "columns": {"sub_month": ["region"]},
            "empty": False,
        },
    )
    monkeypatch.setattr(
        catalog_client,
        "introspect",
        lambda **_kw: {"tables": 1, "columns": 1},
    )
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **_kw: {
            "tables": [
                {
                    "schema_name": "biz",
                    "table_name": "sub_month",
                    "columns": [{"name": "region"}],
                }
            ]
        },
    )

    def capture_put(**kwargs):
        put_calls.append(kwargs)
        return {"tables": 1, "columns": 1}

    monkeypatch.setattr(catalog_client, "put_grants", capture_put)

    seed_demo_catalog_grants(seeded_engine)
    assert put_calls == []


def test_seed_puts_when_effective_empty(seeded_engine, monkeypatch):
    put_calls: list[dict] = []

    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {"tables": [], "columns": {}, "empty": True},
    )
    monkeypatch.setattr(
        catalog_client,
        "introspect",
        lambda **_kw: {"tables": 2, "columns": 4},
    )
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **_kw: {
            "tables": [
                {
                    "schema_name": "biz",
                    "table_name": "sub_month",
                    "columns": [{"name": "region"}, {"name": "sub_cnt"}],
                },
                {
                    "schema_name": "biz",
                    "table_name": "channel_day",
                    "columns": [{"name": "day"}, {"name": "channel"}],
                },
            ]
        },
    )

    def capture_put(**kwargs):
        put_calls.append(kwargs)
        return {"tables": 2, "columns": 4}

    monkeypatch.setattr(catalog_client, "put_grants", capture_put)

    seed_demo_catalog_grants(seeded_engine)
    assert len(put_calls) == 1
    names = {t["table_name"] for t in put_calls[0]["tables"]}
    assert names == {"sub_month", "channel_day"}
    sub = next(t for t in put_calls[0]["tables"] if t["table_name"] == "sub_month")
    assert sub["columns"] == ["region", "sub_cnt"]

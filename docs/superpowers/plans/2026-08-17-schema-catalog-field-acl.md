# Schema Catalog & Field ACL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an external Catalog service for datasource schema introspection, workspace-level table/column grants, main-API proxy + Ask enforcement (empty grants deny; unauthorized columns rejected), and Datasources UI to browse/authorize.

**Architecture:** Shared `apps/engine/schema_introspect.py` (Postgres-first). Catalog FastAPI app stores snapshots + grants. Main API proxies with ACL and fetches `effective` before Ask. `column_guard` + table whitelist replace Pack `table_whitelist` as Ask truth. Seed pre-grants demo biz tables.

**Tech Stack:** FastAPI, SQLModel, sqlglot, SQLAlchemy, Vue 3, Docker Compose, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-schema-catalog-field-acl-design.md`

**Clean-room:** Never open or copy SQLBot-main.

**Branch:** `feature/schema-catalog` from latest `main`.

**Git author (do not git config):** `GIT_AUTHOR_NAME=zhouxd1` `GIT_AUTHOR_EMAIL=zhouxd1@users.noreply.github.com` (same for committer).

---

## File map

| Path | Responsibility |
|---|---|
| `apps/engine/schema_introspect.py` | Probe tables/columns given Engine + db_type (Postgres first) |
| `apps/engine/column_guard.py` | `assert_columns_allowed(sql, allowed_columns_by_table, dialect)` |
| `apps/catalog/` | Catalog FastAPI app: models, db, routes `/v1/*`, settings |
| `docker/catalog.Dockerfile` | Catalog image |
| `docker/docker-compose.yml` | `catalog` service + env |
| `docker/init/02_catalog_schema.sql` | Optional `CREATE SCHEMA catalog` |
| `apps/api/catalog_client.py` | HTTP client to Catalog |
| `apps/api/settings.py` | `catalog_base_url` |
| `apps/api/routes_datasources.py` | Proxy introspect/schema/grants |
| `apps/api/rls_load.py` / ask paths | Load effective; deny if empty |
| `apps/engine/ask.py` | Accept table_whitelist + column map + prompt; run column_guard |
| `apps/api/init_db.py` or `scripts/seed_catalog_grants.py` | Demo grants after introspect |
| `web/src/views/admin/DatasourcesView.vue` | Refresh + authorize UI |
| `web/src/api.ts` | schema/grants helpers |
| `tests/test_schema_introspect.py` | Probe against sqlite/postgres fixtures |
| `tests/test_column_guard.py` | Column allow/deny |
| `tests/test_catalog_api.py` | Catalog TestClient |
| `tests/test_datasource_schema_proxy.py` | Main API proxy + ACL |
| `tests/test_ask_catalog_grants.py` | Empty deny; column reject; happy path |

---

### Task 1: Branch + schema_introspect + column_guard

**Files:**
- Create: `apps/engine/schema_introspect.py`, `apps/engine/column_guard.py`
- Create: `tests/test_schema_introspect.py`, `tests/test_column_guard.py`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b feature/schema-catalog
```

- [ ] **Step 2: Failing column_guard tests**

```python
# tests/test_column_guard.py
from apps.engine.column_guard import assert_columns_allowed
from apps.engine.sql_guard import SqlGuardError
import pytest

def test_allows_whitelisted_columns():
    sql = "SELECT region, sub_cnt FROM biz.sub_month"
    allowed = {"sub_month": {"region", "sub_cnt", "arpu"}}
    assert_columns_allowed(sql, allowed, dialect="postgres")  # no raise

def test_rejects_unknown_column():
    sql = "SELECT region, secret FROM biz.sub_month"
    allowed = {"sub_month": {"region", "sub_cnt"}}
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")

def test_star_rejected_when_not_all_columns_granted():
    sql = "SELECT * FROM biz.sub_month"
    allowed = {"sub_month": {"region"}}
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")
```

- [ ] **Step 3: Implement `column_guard.py`** using sqlglot: collect column refs for tables in allow map; `*` → reject unless allowed set is marked complete (v1: always reject `*`); unqualified cols match if single-table; multi-table unqualified → reject.

- [ ] **Step 4: `schema_introspect.py`**

```python
def introspect_tables(engine: Engine, *, db_type: str = "postgres") -> list[dict]:
    """Return [{schema_name, table_name, columns: [{name, data_type, nullable}]}].
    Postgres: information_schema for schemas in ('biz','network','cs') plus public if needed.
    SQLite: use inspector for demo tests.
    """
```

Test with sqlite in-memory create table.

- [ ] **Step 5: pytest + commit** `feat: add schema introspect and column guard`

---

### Task 2: Catalog service skeleton (models + grants + effective)

**Files:**
- Create: `apps/catalog/__init__.py`, `settings.py`, `db.py`, `models.py`, `main.py`, `routes.py`
- Create: `tests/test_catalog_api.py`

- [ ] **Step 1: Models** (SQLModel, schema `catalog` via `__table_args__ = {"schema": "catalog"}` or table names prefixed `catalog_` in public — **prefer prefixed table names in default schema** for SQLite test simplicity: `ti_catalog_table`, etc. OR use same Postgres schema only in compose and sqlite without schema in tests.)

**Decision locked:** Use table names `cat_datasource_ref`, `cat_table`, `cat_column`, `cat_ws_table_grant`, `cat_ws_column_grant` in the Catalog DB (default schema) so SQLite tests work.

- [ ] **Step 2: Catalog app** with:

```python
# POST /v1/introspect
# body: {workspace_id, datasource_id, db_type, sqlalchemy_url}  # short-lived URL built by main API
# clears old tables for ds, inserts introspect results

# GET /v1/workspaces/{workspace_id}/schema?datasource_id=
# PUT /v1/workspaces/{workspace_id}/grants
# body: {datasource_id, tables: [{schema_name, table_name, columns: [str]}]}
# GET /v1/workspaces/{workspace_id}/effective?datasource_id=
# → {tables: ["sub_month", ...], columns: {"sub_month": ["region", ...]}, empty: bool}
```

- [ ] **Step 3: Tests** with Catalog TestClient + temp sqlite URL env.

- [ ] **Step 4: commit** `feat: add catalog service for schema grants`

---

### Task 3: Docker + main API catalog client + datasource proxy

**Files:**
- Create: `docker/catalog.Dockerfile`
- Modify: `docker/docker-compose.yml`, `apps/api/settings.py`, `apps/api/routes_datasources.py`
- Create: `apps/api/catalog_client.py`
- Create: `tests/test_datasource_schema_proxy.py`

- [ ] **Step 1: settings** `catalog_base_url: str = "http://127.0.0.1:8001"` (`TI_CATALOG_BASE_URL`)

- [ ] **Step 2: catalog_client** — `introspect`, `get_schema`, `put_grants`, `get_effective` with httpx timeout; on connection error raise HTTP 503 with clear message.

- [ ] **Step 3: Proxy routes** (replace stub introspect):
  - Build sqlalchemy URL via existing `build_sqlalchemy_url` + decrypted password
  - Call catalog; never log password
  - GET schema: any workspace member; PUT grants: org_admin / `_require_ds_manage`

- [ ] **Step 4: Compose**

```yaml
  catalog:
    build:
      context: ..
      dockerfile: docker/catalog.Dockerfile
    environment:
      TI_CATALOG_DATABASE_URL: postgresql+psycopg://postgres:telecom@db:5432/telecom
    ports:
      - "8001:8001"
    depends_on:
      db:
        condition: service_healthy
  api:
    environment:
      TI_CATALOG_BASE_URL: http://catalog:8001
    depends_on:
      - catalog
```

Catalog uvicorn: `apps.catalog.main:app --host 0.0.0.0 --port 8001`

- [ ] **Step 5: pytest proxy with monkeypatched catalog_client + commit** `feat: proxy datasource schema APIs to catalog`

---

### Task 4: AskEngine + ask paths use Catalog effective

**Files:**
- Modify: `apps/engine/ask.py`, `apps/api/main.py`, `apps/api/routes_sessions.py`, `apps/api/deps.py` if needed
- Create: `apps/api/catalog_effective.py` helper
- Create: `tests/test_ask_catalog_grants.py`

- [ ] **Step 1: AskEngine.ask** kwargs:

```python
table_whitelist: set[str] | list[str] | None = None,  # if None, use pack.table_whitelist for backward compat in unit tests
allowed_columns: dict[str, set[str]] | None = None,
```

When `table_whitelist` provided, use it in `guard_sql` instead of `pack.table_whitelist`.  
When `allowed_columns` provided, after guard run `assert_columns_allowed`; append column allow list to terminology prompt.

- [ ] **Step 2: API ask paths**

```python
eff = catalog_client.get_effective(workspace_id, datasource_id)
if eff.get("empty"):
    raise HTTPException(403, detail="请先在数据源中授权表字段")
engine.ask(..., table_whitelist=eff["tables"], allowed_columns={k: set(v) for k,v in eff["columns"].items()}, rls_predicates=...)
```

Order: effective → guard tables → column_guard → apply_rls → guard again.

- [ ] **Step 3: Tests** — mock catalog effective empty → 403; partial columns → FakeLLM SQL with bad col → error; good cols → ok.

- [ ] **Step 4: commit** `feat: enforce catalog table and column grants on ask`

---

### Task 5: Demo seed grants

**Files:**
- Modify: `apps/api/init_db.py` or add `apps/api/seed_catalog.py` called from lifespan when `TI_CATALOG_BASE_URL` reachable
- Modify: tests that assume Pack-only whitelist still pass locally by mocking effective OR seeding grants in fixture

- [ ] **Step 1:** After tenant bootstrap, if catalog up: introspect default ds; PUT grants for `biz.sub_month` + `biz.channel_day` all columns from snapshot (idempotent).

- [ ] **Step 2:** Ensure `client_with_seed` / ask tests either mock `get_effective` returning full demo columns OR run catalog app in-process in conftest.

**Locked approach for tests:** `conftest` fixture starts Catalog app with shared sqlite via httpx ASGITransport **or** monkeypatch `catalog_client.get_effective` in unit tests; add one integration test with ASGI both apps.

- [ ] **Step 3: commit** `feat: seed demo catalog grants for biz tables`

---

### Task 6: Frontend Datasources schema UI

**Files:**
- Modify: `web/src/api.ts`, `web/src/views/admin/DatasourcesView.vue`

- [ ] **Step 1: API helpers** — `introspectDatasource`, `fetchDatasourceSchema`, `saveDatasourceGrants`

- [ ] **Step 2: UI** — buttons「刷新结构」「字段授权」; drawer with checkboxes tree; checking table checks all columns by default; save PUT grants; org_admin only for write.

- [ ] **Step 3: `npm run build` + commit** `feat: add datasource schema browse and grant UI`

---

### Task 7: README + full acceptance

- [ ] **Step 1: README** — Catalog port 8001, authorize flow, empty grants deny ask
- [ ] **Step 2: `pytest -v` + `npm run build`**
- [ ] **Step 3: commit** `docs: schema catalog and field ACL notes`

---

## Self-review (plan vs spec)

| Spec item | Task |
|---|---|
| External Catalog service | 2, 3 |
| Introspect + snapshot | 1, 2 |
| Workspace table/column grants | 2, 3, 6 |
| Empty → deny ask | 4 |
| Column reject not mask | 1, 4 |
| Pack not table truth | 4, 5 |
| Proxy ACL | 3 |
| Demo seed grants | 5 |
| UI browse/authorize | 6 |
| Compose | 3 |
| pytest + build | 1–7 |

**Names locked:** `introspect_tables`, `assert_columns_allowed`, `cat_*` models, `catalog_client`, `effective.empty`, `TI_CATALOG_BASE_URL`.

---

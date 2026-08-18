# Schema Browser, Metadata & Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drill-in from the datasource list to a left table tree and right structure/data pane, with full probed metadata, grants on the structure grid, and read-only preview (LIMIT + RLS).

**Architecture:** Extend `introspect_tables` and Catalog snapshot columns. Main API `GET /admin/datasources/{id}/preview` builds a single-table SELECT from snapshot identifiers only, then `guard_sql` + `apply_rls` + `execute_select`. Vue keeps `/app/datasources`: list vs browse state; extract `DatasourceBrowser.vue`.

**Tech Stack:** FastAPI, SQLModel, sqlglot/RLS helpers, SQLAlchemy, Vue 3, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-schema-browser-preview-design.md`

**Clean-room:** Never open or copy SQLBot-main.

**Branch:** continue `feature/schema-catalog`.

**Git author (do not git config):** `GIT_AUTHOR_NAME=zhouxd1` `GIT_AUTHOR_EMAIL=zhouxd1@users.noreply.github.com` (same for committer).

---

## File map

| Path | Responsibility |
|---|---|
| `apps/engine/schema_introspect.py` | Probe table_kind/comment + column ordinal/default/pk/comment; full type string |
| `apps/engine/ident.py` | `quote_ident` — snapshot names only, dialect quotes |
| `apps/engine/preview_sql.py` | `build_preview_sql(schema, table, columns, *, dialect, limit)` |
| `apps/catalog/models.py` | Extra columns on `CatTable` / `CatColumn` |
| `apps/catalog/migrate.py` | ADD COLUMN for existing Catalog DBs (`create_all` does not alter) |
| `apps/catalog/main.py` | Call migrate in lifespan |
| `apps/catalog/routes.py` | Persist and return extra metadata on schema JSON |
| `apps/api/routes_datasources.py` | `GET /{ds_id}/preview` |
| `web/src/api.ts` | Types + `previewDatasourceTable` |
| `web/src/views/admin/DatasourceBrowser.vue` | Tree + 结构/数据 + grants |
| `web/src/views/admin/DatasourcesView.vue` | List click → browse; drop list-row 刷新/授权 buttons |
| `README.md` | Browse vs Ask ACL note |
| `tests/test_schema_introspect.py` | Rich metadata on sqlite |
| `tests/test_preview_sql.py` | Quote + reject bad identifiers |
| `tests/test_catalog_api.py` | Schema JSON includes new fields |
| `tests/test_datasource_preview.py` | Preview ACL, 404, RLS, no empty-grant 403 |

---

### Task 1: Rich introspect metadata

**Files:**
- Modify: `apps/engine/schema_introspect.py`
- Test: `tests/test_schema_introspect.py`

- [ ] **Step 1: Extend sqlite introspect test**

Add to `tests/test_schema_introspect.py`:

```python
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from apps.engine.schema_introspect import introspect_tables


def test_introspect_sqlite_includes_pk_default_ordinal():
    engine = create_engine("sqlite:///:memory:")
    meta = MetaData()
    Table(
        "sub_month",
        meta,
        Column("id", Integer, primary_key=True),
        Column("region", String, nullable=False, server_default="华东"),
        Column("sub_cnt", Integer, nullable=True),
    )
    meta.create_all(engine)
    rows = introspect_tables(engine, db_type="sqlite")
    table = next(r for r in rows if r["table_name"] == "sub_month")
    assert table["table_kind"] in {"table", "BASE TABLE"}
    assert "table_comment" in table
    cols = {c["name"]: c for c in table["columns"]}
    assert cols["id"]["is_primary_key"] is True
    assert cols["region"]["is_primary_key"] is False
    assert cols["id"]["ordinal_position"] == 1
    assert cols["region"]["ordinal_position"] == 2
    assert cols["sub_cnt"]["nullable"] is True
    assert "column_default" in cols["region"]
    assert "column_comment" in cols["region"]
```

- [ ] **Step 2: Run failing test**

Run: `python -m pytest tests/test_schema_introspect.py::test_introspect_sqlite_includes_pk_default_ordinal -v`

Expected: FAIL (`table_kind` / `is_primary_key` KeyError)

- [ ] **Step 3: Implement richer `_col_dict` and probes**

Replace `_col_dict` and sqlite/postgres probes in `apps/engine/schema_introspect.py`.

Column dict shape (locked):

```python
{
    "name": str,
    "data_type": str,
    "nullable": bool,
    "ordinal_position": int,
    "column_default": str | None,
    "is_primary_key": bool,
    "column_comment": str | None,
}
```

Table dict shape (locked):

```python
{
    "schema_name": str,
    "table_name": str,
    "table_kind": str,       # "table" | "view" | inspector value
    "table_comment": str | None,
    "columns": list[dict],
}
```

SQLite: `inspect.get_columns` (`default`, `nullable`); `inspect.get_pk_constraint` for PK names; `get_table_comment` if present else `None`; `table_kind="table"`; views via `get_view_names` with `table_kind="view"`. Ordinal = 1-based enumerate.

Postgres: keep schema filter `('biz','network','cs')`. Use `information_schema.columns` for `column_default`, `ordinal_position`, `is_nullable`, and format `data_type`:

- if `character_maximum_length` set → `f"{data_type}({character_maximum_length})"`
- elif `numeric_precision` set → `f"{data_type}({numeric_precision},{numeric_scale or 0})"`
- else `data_type`

PK: `information_schema.table_constraints` + `key_column_usage` where `constraint_type = 'PRIMARY KEY'`.

Comments (same connection, ignore errors → None):

```sql
SELECT n.nspname AS schema_name, c.relname AS table_name,
       obj_description(c.oid, 'pg_class') AS table_comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('biz','network','cs')
```

```sql
SELECT n.nspname, c.relname, a.attname,
       col_description(c.oid, a.attnum) AS column_comment
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE a.attnum > 0 AND NOT a.attisdropped
  AND n.nspname IN ('biz','network','cs')
```

`table_kind` from `information_schema.tables.table_type` (`BASE TABLE` → store `"table"`, `VIEW` → `"view"`).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_schema_introspect.py -v`

Expected: PASS (including existing tests; extra keys OK)

- [ ] **Step 5: Commit**

```bash
git add apps/engine/schema_introspect.py tests/test_schema_introspect.py
git commit -m "feat: probe table and column metadata on introspect"
```

---

### Task 2: Persist metadata on Catalog snapshot + schema API

**Files:**
- Modify: `apps/catalog/models.py`
- Create: `apps/catalog/migrate.py`
- Modify: `apps/catalog/main.py`
- Modify: `apps/catalog/routes.py`
- Test: `tests/test_catalog_api.py`

- [ ] **Step 1: Failing assertion on schema JSON**

In `tests/test_catalog_api.py` after introspect in `test_introspect_schema_grants_effective`, add:

```python
    sub = by_name["sub_month"]
    assert sub["table_kind"] in {"table", "view"}
    assert "table_comment" in sub
    region = next(c for c in sub["columns"] if c["name"] == "region")
    assert "ordinal_position" in region
    assert "column_default" in region
    assert "is_primary_key" in region
    assert "column_comment" in region
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_catalog_api.py::test_introspect_schema_grants_effective -v`

Expected: FAIL KeyError `table_kind`

- [ ] **Step 3: Models + migrate + persist + GET schema**

`CatTable` add:

```python
table_kind: str = "table"
table_comment: str = ""
```

`CatColumn` add:

```python
ordinal_position: int = 0
column_default: str = ""
is_primary_key: bool = False
column_comment: str = ""
```

`apps/catalog/migrate.py`:

```python
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_COLUMNS = [
    ("cat_table", "table_kind", "VARCHAR DEFAULT 'table'"),
    ("cat_table", "table_comment", "VARCHAR DEFAULT ''"),
    ("cat_column", "ordinal_position", "INTEGER DEFAULT 0"),
    ("cat_column", "column_default", "VARCHAR DEFAULT ''"),
    ("cat_column", "is_primary_key", "BOOLEAN DEFAULT 0"),
    ("cat_column", "column_comment", "VARCHAR DEFAULT ''"),
]

def ensure_catalog_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, col_type in _COLUMNS:
            if table not in names:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
```

In `apps/catalog/main.py` lifespan after `create_all`, call `ensure_catalog_columns(get_engine())`.

In `post_introspect` when creating `CatTable` / `CatColumn`, map from introspect dict (`col.get("name")` etc.). Empty comment/default → `""`.

In `get_schema` table object include `table_kind`, `table_comment`; each column include `ordinal_position`, `column_default`, `is_primary_key`, `column_comment` (plus existing name/type/nullable/granted).

Do **not** delete grants in `_clear_snapshot` (already only clears `cat_table`/`cat_column`).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_catalog_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/catalog/models.py apps/catalog/migrate.py apps/catalog/main.py apps/catalog/routes.py tests/test_catalog_api.py
git commit -m "feat: store and return full catalog column metadata"
```

---

### Task 3: Safe preview SQL builder

**Files:**
- Create: `apps/engine/ident.py`
- Create: `apps/engine/preview_sql.py`
- Create: `tests/test_preview_sql.py`

- [ ] **Step 1: Failing tests**

Create `tests/test_preview_sql.py`:

```python
import pytest

from apps.engine.preview_sql import build_preview_sql
from apps.engine.sql_guard import SqlGuardError


def test_build_preview_sql_postgres():
    sql = build_preview_sql(
        "biz",
        "sub_month",
        ["region", "sub_cnt"],
        dialect="postgres",
        limit=50,
    )
    assert sql == 'SELECT "region", "sub_cnt" FROM "biz"."sub_month" LIMIT 51'


def test_build_preview_sql_sqlite_main_omits_schema():
    sql = build_preview_sql(
        "main",
        "sub_month",
        ["region"],
        dialect="sqlite",
        limit=50,
    )
    assert sql == 'SELECT "region" FROM "sub_month" LIMIT 51'


def test_rejects_bad_identifier():
    with pytest.raises(SqlGuardError):
        build_preview_sql("biz", "sub_month;drop", ["region"], dialect="postgres", limit=50)
```

Limit in SQL is `limit + 1` so `execute_select(..., max_rows=limit)` can set `truncated`.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_preview_sql.py -v`

Expected: FAIL import error

- [ ] **Step 3: Implement `quote_ident` and `build_preview_sql`**

`apps/engine/ident.py`:

```python
import re

from apps.engine.sql_guard import SqlGuardError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str, dialect: str = "postgres") -> str:
    if not name or not _IDENT.match(name):
        raise SqlGuardError(f"invalid identifier: {name!r}")
    family = (dialect or "postgres").lower()
    if family in {"mysql", "tidb", "oceanbase_mysql", "hive"}:
        return f"`{name}`"
    return f'"{name}"'
```

`apps/engine/preview_sql.py`:

```python
from apps.engine.ident import quote_ident
from apps.engine.sql_guard import SqlGuardError


def build_preview_sql(
    schema_name: str,
    table_name: str,
    columns: list[str],
    *,
    dialect: str = "postgres",
    limit: int = 50,
) -> str:
    if not columns:
        raise SqlGuardError("preview requires columns")
    if limit < 1 or limit > 200:
        raise SqlGuardError("limit must be 1..200")
    cols = ", ".join(quote_ident(c, dialect) for c in columns)
    table = quote_ident(table_name, dialect)
    schema_key = (schema_name or "").lower()
    if schema_key in {"", "main", "public"} and dialect.lower() in {"sqlite", "sqlite3"}:
        from_ = table
    elif schema_key in {"", "main"}:
        from_ = table
    else:
        from_ = f"{quote_ident(schema_name, dialect)}.{table}"
    return f"SELECT {cols} FROM {from_} LIMIT {int(limit) + 1}"
```

For postgres always qualify with schema (`biz.sub_month`). Sqlite `main` omits schema as in the test.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_preview_sql.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/engine/ident.py apps/engine/preview_sql.py tests/test_preview_sql.py
git commit -m "feat: build read-only preview SQL from snapshot identifiers"
```

---

### Task 4: Main API preview endpoint

**Files:**
- Modify: `apps/api/routes_datasources.py`
- Create: `tests/test_datasource_preview.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_datasource_preview.py` using the same sqlite client fixture pattern as `tests/test_datasource_schema_proxy.py` (`init_db`, `seed_tenant_bootstrap`, `TestClient(app)`, analyst headers).

Behaviors:

1. `GET /admin/datasources/{id}/preview` without `schema`+`table` → 422
2. Catalog `get_schema` returns no matching table → 404 `table not in catalog snapshot`
3. Happy path: monkeypatch `get_schema` with `sub_month` columns; monkeypatch `build_engine_from_datasource` to sqlite warehouse with `region`/`secret`; monkeypatch `get_effective` unused (preview must **not** 403 when effective empty — monkeypatch `get_effective` to `empty: True` and still 200)
4. Analyst: seed RLS is on tenant bootstrap for `analyst1`; if using custom analyst without RLS, monkeypatch `load_rls_predicates` to filter `region='华东'` and assert rows
5. `PUT` still 403 for analyst (already covered); preview GET 200 for analyst
6. `limit=50` default; `limit=999` → 422

Sketch for empty-grant must still preview:

```python
def test_preview_ok_when_effective_empty(client, ds_id, tmp_path, monkeypatch):
    warehouse = create_engine(f"sqlite:///{tmp_path / 'wh.db'}")
    with warehouse.begin() as conn:
        conn.execute(text("CREATE TABLE sub_month(region TEXT, secret TEXT)"))
        conn.execute(text("INSERT INTO sub_month VALUES ('华东','x'),('华北','y')"))
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **_k: {
            "tables": [{
                "schema_name": "main",
                "table_name": "sub_month",
                "columns": [
                    {"name": "region"},
                    {"name": "secret"},
                ],
            }]
        },
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_k: {"tables": [], "columns": {}, "empty": True},
    )
    monkeypatch.setattr(
        "apps.api.routes_datasources.build_engine_from_datasource",
        lambda _ds: warehouse,
    )
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=workspace_headers(client),
        params={"schema": "main", "table": "sub_month"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "secret" in body["columns"]
    assert len(body["rows"]) >= 1
    assert "truncated" in body
```

For sqlite default DS created by seed, `ds_id` fixture in proxy tests creates a postgres row — preview will use that row's engine unless monkeypatched. Follow proxy test `ds_id` + monkeypatch engine.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_datasource_preview.py -v`

Expected: FAIL 404 on unknown route

- [ ] **Step 3: Implement route**

In `apps/api/routes_datasources.py` add (imports: `Query`, `get_current_user`, `load_rls_predicates`, `get_workspace_member`, `build_engine_from_datasource`, `dialect_for_datasource`, `build_preview_sql`, `guard_sql`, `apply_rls`, `execute_select`, `SqlGuardError`).

```python
@router.get("/{ds_id}/preview")
def preview_datasource_table(
    ds_id: int,
    schema: str = Query(..., min_length=1),
    table: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
    user: TiUser = Depends(get_current_user),
) -> dict[str, Any]:
    workspace, _access = ws_access
    row = _get_workspace_ds(session, ds_id, workspace)
    tree = catalog_client.get_schema(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        datasource_id=ds_id,
    )
    match = next(
        (
            t
            for t in (tree.get("tables") or [])
            if t.get("schema_name") == schema and t.get("table_name") == table
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="table not in catalog snapshot")
    col_names = [c["name"] for c in (match.get("columns") or []) if c.get("name")]
    dialect = dialect_for_datasource(row)
    try:
        sql = build_preview_sql(
            schema, table, col_names, dialect=dialect, limit=limit
        )
        sql = guard_sql(sql, {table}, dialect=dialect)
        member = get_workspace_member(session, workspace.id, user.id)  # type: ignore[arg-type]
        preds = load_rls_predicates(session, user, workspace, member)
        if preds:
            sql = apply_rls(sql, preds, dialect=dialect)
            sql = guard_sql(sql, {table}, dialect=dialect)
        engine = build_engine_from_datasource(row)
        try:
            rows, truncated = execute_select(engine, sql, max_rows=limit)
        finally:
            engine.dispose()
    except SqlGuardError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="数据源连接失败，请检查数据源配置后重试。",
        )
    return {"columns": col_names, "rows": rows, "truncated": truncated}
```

Do **not** call `get_effective`. Never log password.

Wire `build_engine_from_datasource` import from `apps.engine.connectors`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_datasource_preview.py tests/test_datasource_schema_proxy.py tests/test_ask_catalog_grants.py -v`

Expected: PASS (Ask empty 403 unchanged)

- [ ] **Step 5: Commit**

```bash
git add apps/api/routes_datasources.py tests/test_datasource_preview.py
git commit -m "feat: add datasource table preview endpoint"
```

---

### Task 5: Datasource list drill-in browser UI

**Files:**
- Modify: `web/src/api.ts`
- Create: `web/src/views/admin/DatasourceBrowser.vue`
- Modify: `web/src/views/admin/DatasourcesView.vue`

- [ ] **Step 1: API types and helper**

Extend `DatasourceSchemaTable` / `DatasourceSchemaColumn` in `web/src/api.ts`:

```typescript
export type DatasourceSchemaColumn = {
  name: string;
  data_type: string;
  nullable: boolean;
  granted: boolean;
  ordinal_position?: number;
  column_default?: string | null;
  is_primary_key?: boolean;
  column_comment?: string | null;
};

export type DatasourceSchemaTable = {
  schema_name: string;
  table_name: string;
  granted: boolean;
  table_kind?: string;
  table_comment?: string | null;
  columns: DatasourceSchemaColumn[];
};

export type DatasourcePreview = {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
};

export async function previewDatasourceTable(
  id: number,
  schema: string,
  table: string,
  limit = 50,
): Promise<DatasourcePreview> {
  const { data } = await client.get<DatasourcePreview>(
    `/admin/datasources/${id}/preview`,
    { params: { schema, table, limit } },
  );
  return data;
}
```

- [ ] **Step 2: `DatasourceBrowser.vue`**

New component props: `ds: Datasource`, `isOrgAdmin: boolean`. Emits: `back`, `note`, `error`.

Layout:

- Header: button `← 返回列表`, title `{ds.name} · {ds.db_type}`, button `刷新结构` (`disabled` if not admin)
- Empty tree: 「暂无探测结果。请先点击刷新结构。」
- Left: group tables by `schema_name`; click table sets `selected`
- Right tabs: `结构` | `数据` (default 结构)
- Structure: table meta line (`table_kind`, `table_comment` or `—`, no indexes)
- Column grid: 授权 checkbox, 列, 类型, 可空, 默认, 主键, 注释 — missing → `—`
- Checkbox `disabled` when `!isOrgAdmin`; admin toggle table = all columns (same logic as current grants modal); persist with `saveDatasourceGrants` (admin only) — debounce or explicit **保存授权** button on the structure pane (keep explicit save to avoid accidental PUT)
- Data tab: `previewDatasourceTable` on selected table; render HTML table; if `truncated` show 「已截断」

Do not copy SQLBot markup. Reuse `admin-shared.css` / existing banners.

- [ ] **Step 3: Wire `DatasourcesView.vue`**

- `browsing` ref `Datasource | null`
- Click `<tr>` → `browsing = row` **except** when click target is inside `.actions` (`@click` on tr + `@click.stop` on `.actions`)
- `role="button"` + Enter/Space on row for keyboard
- When `browsing`: hide list table; show `DatasourceBrowser`
- Remove list-row buttons 「刷新结构」「字段授权」 and the grants modal
- Keep 测连/设默认/编辑/删除 on list
- Banner: members can enter browse; only admin refreshes/saves grants

- [ ] **Step 4: Build**

Run: `cd web && npm run build`

Expected: exit 0

- [ ] **Step 5: Commit**

```bash
git add web/src/api.ts web/src/views/admin/DatasourceBrowser.vue web/src/views/admin/DatasourcesView.vue
git commit -m "feat: drill-in datasource schema browser with preview"
```

---

### Task 6: README + full test

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README**

Under Schema Catalog section add:

- 数据源列表点一行进入库表浏览（结构含类型/默认/主键/注释；数据为只读预览）
- 预览不检查字段授权；问数仍空授权拒绝、未授权列拒绝
- 仅 org_admin 可刷新结构与保存勾选

- [ ] **Step 2: pytest + build**

Run: `python -m pytest -q`  
Expected: all pass  

Run: `cd web && npm run build`  
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: schema browser and preview notes"
```

---

## Self-review (plan vs spec)

| Spec item | Task |
|---|---|
| 点数据源进入 / 返回列表 | 5 |
| 左树右结构\|数据 | 5 |
| 完整表/列元数据 | 1, 2, 5 |
| 结构勾选授权，仅 admin 写 | 5 + existing PUT ACL |
| 成员可预览未授权列 | 4 (no effective check) |
| Ask 规则不变 | 4 regression tests |
| Preview LIMIT 50..200, truncated | 3, 4 |
| RLS on preview | 4 |
| Snapshot identifiers only | 3 |
| Catalog 不存样例 | 4 (live SELECT) |
| 刷新不清空 grants | 2 (existing `_clear_snapshot`) |
| 不做侧栏库表页 / 索引外键 / SQLBot | 5 + clean-room |
| pytest + build | 6 |

**Names locked:** `build_preview_sql`, `quote_ident`, `ensure_catalog_columns`, `previewDatasourceTable`, `DatasourceBrowser.vue`.

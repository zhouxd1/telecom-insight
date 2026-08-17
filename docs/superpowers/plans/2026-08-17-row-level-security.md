# Row-Level Security (RLS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver workspace-member row filters via `ti_rls_policy`, Prompt hints + SQL Guard-path rewrite (`in`/`eq`), and org-level `rls_admin_bypass`, with admin UI in workspace members.

**Architecture:** Policies live in `ti_rls_policy` (FK to `ti_workspace_member`). Ask loads policies unless org_admin + bypass. `apps/engine/rls.py` merges predicates (same column OR, different columns AND) and rewrites SELECT via sqlglot; unsafe rewrites raise `SqlGuardError`. Column catalog is a static/domain map aligned with pack whitelists.

**Tech Stack:** FastAPI, SQLModel, sqlglot, Vue 3, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-row-level-security-design.md`

**Clean-room:** Never open or copy SQLBot-main.

**Branch:** `feature/rls` from latest `main`.

**Git author (do not git config):** `GIT_AUTHOR_NAME=zhouxd1` `GIT_AUTHOR_EMAIL=zhouxd1@users.noreply.github.com` (same for committer).

---

## File map

| Path | Responsibility |
|---|---|
| `apps/api/models_db.py` | `TiOrg.rls_admin_bypass`; `TiRlsPolicy` |
| `apps/api/rls_columns.py` | Domain → allowed filterable columns |
| `apps/engine/rls.py` | `RlsPredicate`, `merge_predicates`, `apply_rls`, `format_rls_prompt` |
| `apps/engine/ask.py` | Accept policies; prompt + rewrite after `guard_sql` |
| `apps/api/routes_rls.py` | Member policy CRUD + org settings + column catalog |
| `apps/api/schemas.py` | `RlsPolicyOut/Create/Update`, `RlsSettingsOut/Update` |
| `apps/api/main.py` | Include router; legacy `/ask` pass policies |
| `apps/api/routes_sessions.py` | Session ask pass policies |
| `apps/api/init_db.py` | Seed bypass + sample analyst policy |
| `web/src/api.ts` | RLS API helpers |
| `web/src/views/admin/WorkspacesView.vue` | Member RLS panel |
| `web/src/views/admin/UsersView.vue` or small settings block | Org bypass toggle (prefer UsersView header if org_admin) |
| `tests/test_rls_rewrite.py` | Merge + rewrite unit tests |
| `tests/test_rls_api.py` | CRUD / ACL / columns / bypass |

---

### Task 1: Branch + model + column catalog + seed

**Files:**
- Create: `apps/api/rls_columns.py`
- Modify: `apps/api/models_db.py`, `apps/api/init_db.py`
- Create: `tests/test_rls_columns.py`

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feature/rls
```

- [ ] **Step 2: Failing test**

```python
# tests/test_rls_columns.py
from apps.api.rls_columns import list_rls_columns, is_allowed_column

def test_biz_has_region():
    cols = list_rls_columns("biz")
    assert any(c["table_name"] == "sub_month" and c["column_name"] == "region" for c in cols)

def test_reject_unknown_column():
    assert is_allowed_column("biz", "biz", "sub_month", "region")
    assert not is_allowed_column("biz", "biz", "sub_month", "not_a_col")
```

- [ ] **Step 3: Run — expect FAIL**

Run: `pytest tests/test_rls_columns.py -v`

- [ ] **Step 4: Implement catalog + model + seed**

`rls_columns.py`:

```python
# schema_name, table_name, column_name, label
_CATALOG: dict[str, list[dict[str, str]]] = {
    "biz": [
        {"schema_name": "biz", "table_name": "sub_month", "column_name": "region", "label": "区域"},
        {"schema_name": "biz", "table_name": "channel_day", "column_name": "channel", "label": "渠道"},
    ],
    "network": [],
    "cs": [],
}

def list_rls_columns(domain: str) -> list[dict[str, str]]:
    return list(_CATALOG.get(domain, []))

def is_allowed_column(domain: str, schema_name: str, table_name: str, column_name: str) -> bool:
    for c in list_rls_columns(domain):
        if (
            c["schema_name"] == schema_name
            and c["table_name"] == table_name
            and c["column_name"] == column_name
        ):
            return True
    return False
```

`TiOrg`: add `rls_admin_bypass: bool = True`.

`TiRlsPolicy` fields per spec; add to `_MODELS`.

`seed_tenant_bootstrap`:
- Ensure existing orgs get `rls_admin_bypass=True` only when column missing via migration-style setattr on load if needed (SQLModel create_all + default); for existing SQLite/Postgres rows, startup ALTER optional like prior workspace_id pattern — prefer: in seed, `if getattr(demo_org, "rls_admin_bypass", None) is None` N/A once field has default; for Postgres upgrade add idempotent `ALTER TABLE ti_org ADD COLUMN IF NOT EXISTS rls_admin_bypass BOOLEAN DEFAULT TRUE` in `main.py` lifespan or `init_db` (mirror prior workspace_id ALTER).
- Create analyst user `analyst1` / `analyst123` if missing; add to default workspace with domains all; if no RLS policy for that member on `sub_month.region`, insert `op=in`, `values=["华东"]`.

- [ ] **Step 5: pytest + commit**

```bash
pytest tests/test_rls_columns.py tests/test_tenant_models.py -v
git add apps/api/models_db.py apps/api/rls_columns.py apps/api/init_db.py apps/api/main.py tests/test_rls_columns.py
git commit -m "feat: add RLS policy model and column catalog"
```

---

### Task 2: RLS rewrite engine (TDD)

**Files:**
- Create: `apps/engine/rls.py`
- Create: `tests/test_rls_rewrite.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_rls_rewrite.py
from apps.engine.rls import RlsPredicate, apply_rls, merge_predicates, format_rls_prompt
from apps.engine.sql_guard import SqlGuardError
import pytest

def test_merge_same_column_or():
    preds = [
        RlsPredicate("biz", "sub_month", "region", "in", ["华东"]),
        RlsPredicate("biz", "sub_month", "region", "in", ["华北"]),
    ]
    merged = merge_predicates(preds)
    assert ("biz", "sub_month") in merged
    # single region IN with both values or OR of two — either OK if semantically equal
    sql_frag = merged[("biz", "sub_month")]
    assert "华东" in sql_frag and "华北" in sql_frag

def test_apply_rls_simple_select():
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    out = apply_rls(
        "SELECT region, SUM(sub_cnt) AS sub_cnt FROM biz.sub_month GROUP BY region",
        preds,
        dialect="postgres",
    )
    assert "华东" in out
    assert "region" in out.lower()

def test_apply_rls_eq():
    preds = [RlsPredicate("biz", "channel_day", "channel", "eq", ["营业厅"])]
    out = apply_rls(
        "SELECT day, new_users FROM biz.channel_day",
        preds,
        dialect="postgres",
    )
    assert "营业厅" in out

def test_no_matching_table_unchanged():
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    sql = "SELECT 1 AS x"
    assert apply_rls(sql, preds, dialect="postgres") == sql

def test_prompt_mentions_policy():
    text = format_rls_prompt([RlsPredicate("biz", "sub_month", "region", "in", ["华东"])])
    assert "region" in text and "华东" in text
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_rls_rewrite.py -v`

- [ ] **Step 3: Implement `apps/engine/rls.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
import sqlglot
from sqlglot import exp

from apps.engine.sql_guard import SqlGuardError, resolve_sqlglot_dialect

@dataclass(frozen=True)
class RlsPredicate:
    schema_name: str
    table_name: str
    column_name: str
    op: str  # in | eq
    values: tuple[str, ...] | list[str]

def _quote_lit(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"

def _pred_sql(p: RlsPredicate) -> str:
    col = p.column_name  # validated against catalog before call
    vals = list(p.values)
    if p.op == "eq":
        if len(vals) != 1:
            raise SqlGuardError("eq requires exactly one value")
        return f"{col} = {_quote_lit(vals[0])}"
    if p.op == "in":
        if not vals:
            raise SqlGuardError("in requires values")
        return f"{col} IN ({', '.join(_quote_lit(v) for v in vals)})"
    raise SqlGuardError(f"unsupported op: {p.op}")

def merge_predicates(preds: list[RlsPredicate]) -> dict[tuple[str, str], str]:
    """Return map (schema, table) -> AND-combined WHERE fragment (no leading AND)."""
    by_table: dict[tuple[str, str], dict[str, list[str]]] = {}
    for p in preds:
        key = (p.schema_name.lower(), p.table_name.lower())
        by_table.setdefault(key, {})
        by_table[key].setdefault(p.column_name.lower(), []).append(_pred_sql(p))
    out: dict[tuple[str, str], str] = {}
    for table_key, cols in by_table.items():
        col_parts = []
        for _col, frags in cols.items():
            col_parts.append("(" + " OR ".join(frags) + ")" if len(frags) > 1 else frags[0])
        out[table_key] = " AND ".join(col_parts)
    return out

def apply_rls(sql: str, preds: list[RlsPredicate], *, dialect: str = "postgres") -> str:
    if not preds:
        return sql
    merged = merge_predicates(preds)
    read = resolve_sqlglot_dialect(dialect)
    try:
        tree = sqlglot.parse_one(sql, read=read)
    except Exception as e:
        raise SqlGuardError(f"rls parse failed: {e}") from e
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SqlGuardError("rls only supports SELECT")

    # Conservative v1: single SELECT with FROM tables; wrap as
    # SELECT * FROM (orig) AS _ti_rls WHERE <conds for used tables>
    # Better: inject into WHERE of outermost Select when all target tables appear as simple Table nodes.
    used_tables = []
    for t in tree.find_all(exp.Table):
        schema = (t.db or "").lower()
        name = t.name.lower()
        used_tables.append((schema, name))

    needed = []
    for key, frag in merged.items():
        sch, tbl = key
        if any(
            (u_sch == sch or not sch) and u_tbl == tbl
            for u_sch, u_tbl in used_tables
        ):
            needed.append(frag)
        # if policy table not in query, skip

    if not needed:
        return sql

    # Prefer append AND to outermost Select WHERE
    if isinstance(tree, exp.Select):
        for frag in needed:
            tree = tree.where(frag, copy=False)
        return tree.sql(dialect=read)

    raise SqlGuardError("cannot safely apply rls to this SQL")

def format_rls_prompt(preds: list[RlsPredicate]) -> str:
    if not preds:
        return ""
    lines = [
        f"- {p.schema_name}.{p.table_name}.{p.column_name} {p.op} {list(p.values)}"
        for p in preds
    ]
    return "行级权限（必须遵守，即使未写出也会被系统强制注入）:\n" + "\n".join(lines)
```

Refine `apply_rls` until tests pass; if sqlglot `.where(frag)` needs `exp.condition`, use `tree.where(sqlglot.condition(frag))`.

- [ ] **Step 4: pytest + commit**

```bash
pytest tests/test_rls_rewrite.py -v
git add apps/engine/rls.py tests/test_rls_rewrite.py
git commit -m "feat: add RLS SQL rewrite and prompt formatter"
```

---

### Task 3: AskEngine Prompt + rewrite integration

**Files:**
- Modify: `apps/engine/ask.py`
- Modify: `apps/engine/llm.py` only if `generate_sql` needs an extra context string — prefer append to `terminology` or new kwarg `extra_instructions: str = ""`
- Extend: `tests/test_rls_rewrite.py` or `tests/test_ask_pipeline.py`

- [ ] **Step 1: Extend AskEngine.ask**

Add kwargs:

```python
rls_predicates: list[RlsPredicate] | None = None,
```

After building terminology, if predicates:

```python
rls_text = format_rls_prompt(list(rls_predicates or []))
if rls_text:
    terminology = (terminology + "\n" + rls_text).strip()
```

After `guard_sql(...)`:

```python
sql = apply_rls(sql, list(rls_predicates or []), dialect=guard_dialect)
sql = guard_sql(sql, set(pack.table_whitelist), dialect=guard_dialect)  # re-check
```

- [ ] **Step 2: Unit test with FakeLLM** returning unfiltered SQL; engine must still inject filter when predicates passed.

- [ ] **Step 3: commit** `feat: enforce RLS in AskEngine after SQL guard`

---

### Task 4: RLS API (CRUD + settings + columns)

**Files:**
- Create: `apps/api/routes_rls.py`
- Modify: `apps/api/schemas.py`, `apps/api/main.py`
- Create: `tests/test_rls_api.py`

- [ ] **Step 1: Schemas**

```python
class RlsPolicyOut(BaseModel):
    id: int
    workspace_id: int
    member_id: int
    domain: str
    schema_name: str
    table_name: str
    column_name: str
    op: str
    values: list[str]

class RlsPolicyCreate(BaseModel):
    domain: str
    schema_name: str
    table_name: str
    column_name: str
    op: str
    values: list[str]

class RlsPolicyUpdate(BaseModel):
    op: str | None = None
    values: list[str] | None = None
    # optionally allow column change — prefer recreate; allow op/values only

class RlsSettingsOut(BaseModel):
    rls_admin_bypass: bool

class RlsSettingsUpdate(BaseModel):
    rls_admin_bypass: bool
```

- [ ] **Step 2: Routes**

Validate create with `is_allowed_column`; `op in {in,eq}`; values rules; member belongs to workspace; `require_org_admin` on writes.

`GET /domains/{domain_id}/rls-columns` → `list_rls_columns`.

`GET/PATCH /orgs/me/rls-settings` load/update `TiOrg.rls_admin_bypass`.

- [ ] **Step 3: Tests** — org_admin CRUD 200; analyst POST 403; bad column 400; settings patch.

- [ ] **Step 4: commit** `feat: add RLS policy and settings APIs`

---

### Task 5: Wire `/ask` and session ask to load policies

**Files:**
- Modify: `apps/api/main.py`, `apps/api/routes_sessions.py`
- Create helper: `apps/api/rls_load.py` with `load_rls_predicates(session, user, workspace, member) -> list[RlsPredicate]`

```python
def load_rls_predicates(session, user: TiUser, workspace: TiWorkspace, member: TiWorkspaceMember | None) -> list[RlsPredicate]:
    org = session.get(TiOrg, user.org_id)
    if org and user.org_role == "org_admin" and org.rls_admin_bypass:
        return []
    if member is None:
        return []
    rows = session.exec(select(TiRlsPolicy).where(TiRlsPolicy.member_id == member.id)).all()
    return [
        RlsPredicate(r.schema_name, r.table_name, r.column_name, r.op, list(r.values or []))
        for r in rows
    ]
```

Pass into `engine.ask(..., rls_predicates=...)`.

- [ ] **Step 1: API test** — login as seeded analyst1, ask about region ranking; assert result rows only 华东 OR sql contains 华东 (use FakeLLM monkeypatch if LLM not deterministic).

Reuse patterns from `tests/test_ask_datasource_binding.py`.

- [ ] **Step 2: commit** `feat: apply member RLS policies on ask paths`

---

### Task 6: Frontend — member RLS panel + bypass toggle

**Files:**
- Modify: `web/src/api.ts`, `web/src/views/admin/WorkspacesView.vue`
- Modify: `web/src/views/admin/UsersView.vue` (org settings strip) **or** add compact toggle on Workspaces page header for org_admin

- [ ] **Step 1: api.ts helpers** — `listMemberRls`, `createMemberRls`, `updateRlsPolicy`, `deleteRlsPolicy`, `fetchRlsSettings`, `updateRlsSettings`, `fetchRlsColumns`

- [ ] **Step 2: WorkspacesView** — in members modal, per-member expand or button「行权限」opening nested list + add form (domain select → columns filtered → op → values comma/chip → save). Only if `isOrgAdmin`.

- [ ] **Step 3: Bypass toggle** — label「管理员绕过行过滤」bound to `rls_admin_bypass`; PATCH on change.

- [ ] **Step 4: `npm run build` + commit** `feat: add RLS management UI for workspace members`

---

### Task 7: Docs + full acceptance

**Files:**
- Modify: `README.md` — short RLS bullet under Phase 1b / new Phase RLS
- Verify: `pytest -v` and `cd web && npm run build`

- [ ] **Step 1: README** — document member RLS, bypass switch, demo analyst seed

- [ ] **Step 2: Full pytest + build**

- [ ] **Step 3: commit** `docs: row-level security acceptance notes`

- [ ] **Step 4:** Spec §7 checklist for PR/finish

---

## Self-review (plan vs spec)

| Spec item | Task |
|---|---|
| ti_rls_policy + org bypass field | 1 |
| column catalog | 1, 4 |
| merge OR/AND + rewrite + reject unsafe | 2 |
| Prompt + Guard path | 3 |
| CRUD + settings API + ACL | 4 |
| Ask/session wiring | 5 |
| Member UI + bypass toggle | 6 |
| seed analyst 华东 | 1 |
| pytest + build + README | 2–7 |

**Type names locked:** `TiRlsPolicy`, `RlsPredicate`, `apply_rls`, `merge_predicates`, `format_rls_prompt`, `load_rls_predicates`, `rls_admin_bypass`.

---

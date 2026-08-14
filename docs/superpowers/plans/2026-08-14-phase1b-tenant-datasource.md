# Phase 1b Tenant + Multi-DB Datasource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 元景.智数 Phase 1b — org/workspace/members, three roles with domain ACL, switchable multi-DB datasources (P0 incl. Hive + domestic), and workspace-scoped Ask.

**Architecture:** Extend `ti_*` app tables with tenant entities; JWT carries `user_id`/`org_id`; `X-Workspace-Id` scopes requests; ACL helper resolves effective role/domains; datasource connection factory maps `db_type` → `protocol_family` engines; AskEngine executes against resolved warehouse engine (not only `TI_DATABASE_URL`).

**Tech Stack:** FastAPI, SQLModel, passlib/bcrypt, cryptography Fernet (password_enc), SQLAlchemy + dialect drivers (psycopg, PyMySQL, optional pyodbc/jaydebeapi/dmPython), Vue 3 + existing Flat 2.0 UI, pytest.

**Spec:** `docs/superpowers/specs/2026-08-14-phase1b-tenant-datasource-design.md`

**Clean-room:** Never open or copy SQLBot-main.

**Branch:** `feature/phase1b` from latest `main`.

**Git author (do not git config):** `GIT_AUTHOR_NAME=zhouxd1` `GIT_AUTHOR_EMAIL=zhouxd1@users.noreply.github.com` (same for committer).

---

## File map

| Path | Responsibility |
|---|---|
| `apps/api/models_db.py` | Add org/workspace/user/member/datasource; add `workspace_id` to existing tables |
| `apps/api/init_db.py` | create_all + seed org/workspace/demo user/default DS + backfill workspace_id |
| `apps/api/crypto.py` | Fernet encrypt/decrypt for datasource passwords |
| `apps/api/auth.py` | JWT with `sub=user_id`, `org_id` |
| `apps/api/acl.py` | Resolve workspace access, effective role, domains |
| `apps/api/deps.py` | Current user object; workspace context; ACL gates; ask engine from datasource |
| `apps/api/db_types.py` | P0/P1 `db_type` → `protocol_family`, SQLAlchemy URL builders |
| `apps/engine/connectors.py` | `build_engine(datasource)`, `test_connection`, family introspect stubs |
| `apps/engine/sql_guard.py` | Accept sqlglot `read=` dialect from protocol_family |
| `apps/engine/ask.py` | Accept external warehouse engine + dialect hint |
| `apps/api/routes_auth.py` | login + `/auth/me` |
| `apps/api/routes_workspaces.py` | workspaces + members |
| `apps/api/routes_users.py` | `/admin/users` |
| `apps/api/routes_datasources.py` | datasources CRUD/test/default/introspect |
| `apps/api/routes_sessions.py` | Filter by workspace; viewer/domain gates; resolve DS for ask |
| `apps/api/routes_admin.py` | Filter by workspace; role/domain gates |
| `apps/api/main.py` | Wire routers; login uses ti_user |
| `apps/api/settings.py` | `TI_FERNET_KEY`, keep demo seed password for bootstrap |
| `web/src/api.ts` | Workspace header, me/workspaces/users/datasources APIs |
| `web/src/layouts/AppShell.vue` | Workspace switcher; enable nav; show role |
| `web/src/views/admin/DatasourcesView.vue` | Datasource admin UI |
| `web/src/views/admin/WorkspacesView.vue` | Workspace + members UI |
| `web/src/views/admin/UsersView.vue` | Org users UI |
| `web/src/views/ChatView.vue` | Domain filter; viewer UX; empty DS state |
| `web/src/router/index.ts` | New routes |
| `tests/test_tenant_models.py` | Models + seed |
| `tests/test_acl.py` | Role/domain resolution |
| `tests/test_auth_users.py` | Login + me |
| `tests/test_workspaces.py` | Workspace/member APIs |
| `tests/test_datasources.py` | DS CRUD/test/default + ask uses DS |
| `tests/test_multi_db_urls.py` | URL/family mapping for all P0 types |
| `tests/test_sql_guard_dialects.py` | Guard dialects |
| `pyproject.toml` | Optional deps: pymysql, cryptography |

---

### Task 1: Branch + tenant models + workspace_id columns

**Files:**
- Modify: `apps/api/models_db.py`
- Modify: `apps/api/init_db.py`
- Create: `tests/test_tenant_models.py`

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feature/phase1b
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_tenant_models.py
from sqlmodel import Session, SQLModel, create_engine, select

from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.models_db import TiOrg, TiUser, TiWorkspace, TiWorkspaceMember, TiDatasource


def test_seed_creates_org_workspace_demo_and_default_ds(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with Session(engine) as s:
        assert s.exec(select(TiOrg)).first() is not None
        ws = s.exec(select(TiWorkspace)).first()
        assert ws is not None
        user = s.exec(select(TiUser).where(TiUser.username == "demo")).first()
        assert user is not None and user.org_role == "org_admin"
        mem = s.exec(select(TiWorkspaceMember)).first()
        assert mem is not None and "biz" in (mem.domains or [])
        ds = s.exec(select(TiDatasource).where(TiDatasource.is_default == True)).first()  # noqa: E712
        assert ds is not None and ds.workspace_id == ws.id
```

- [ ] **Step 3: Run test — expect FAIL** (missing models/seed)

Run: `pytest tests/test_tenant_models.py -v`  
Expected: FAIL (import or missing function)

- [ ] **Step 4: Implement models** in `apps/api/models_db.py`

Add tables (fields per spec). For SQLite JSON domains use `sa_column=Column(JSON)` or store as Text JSON string — prefer `Column(JSON)` with SQLAlchemy JSON.

Add nullable `workspace_id: Optional[int] = Field(default=None, index=True)` to `TiChatSession`, `TiAiModel`, `TiTerm`, `TiSqlExample`. Add optional `datasource_id` on `TiChatSession`.

Update `_MODELS` tuple to include new tables.

- [ ] **Step 5: Implement `seed_tenant_bootstrap`** in `apps/api/init_db.py`

Idempotent: if any `TiOrg` exists, skip create but still backfill NULL `workspace_id` on legacy rows to default workspace. Hash demo password with passlib bcrypt. Create default datasource with `db_type=postgres` (or `sqlite` in tests when URL is sqlite).

- [ ] **Step 6: pytest pass + commit**

```bash
pytest tests/test_tenant_models.py -v
git add apps/api/models_db.py apps/api/init_db.py tests/test_tenant_models.py
git commit -m "feat: add tenant models and bootstrap seed"
```

---

### Task 2: Crypto + JWT user identity + ACL helper

**Files:**
- Create: `apps/api/crypto.py`, `apps/api/acl.py`
- Modify: `apps/api/auth.py`, `apps/api/settings.py`
- Create: `tests/test_acl.py`, `tests/test_crypto.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_crypto.py
from apps.api.crypto import decrypt_secret, encrypt_secret

def test_roundtrip(monkeypatch):
    monkeypatch.setenv("TI_FERNET_KEY", "")  # crypto module derives stable dev key from jwt_secret if empty
    from importlib import reload
    import apps.api.settings as st
    import apps.api.crypto as c
    reload(st)
    reload(c)
    token = c.encrypt_secret("s3cret")
    assert token != "s3cret"
    assert c.decrypt_secret(token) == "s3cret"
```

```python
# tests/test_acl.py
from apps.api.acl import EffectiveAccess, resolve_access

def test_org_admin_gets_all_domains():
    access = resolve_access(
        org_role="org_admin",
        member_role=None,
        member_domains=None,
        is_org_admin=True,
    )
    assert access.role == "org_admin"
    assert set(access.domains) == {"biz", "network", "cs"}

def test_viewer_cannot_ask():
    access = resolve_access(
        org_role="viewer",
        member_role="viewer",
        member_domains=["biz"],
        is_org_admin=False,
    )
    assert access.can_ask is False
    assert access.can_manage_users is False
```

- [ ] **Step 2: Implement**

`settings.py` add: `fernet_key: str = ""`

`crypto.py`:

```python
import base64
import hashlib
from cryptography.fernet import Fernet
from apps.api.settings import settings

def _fernet() -> Fernet:
    raw = settings.fernet_key or settings.jwt_secret
    digest = hashlib.sha256(raw.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
```

`acl.py`:

```python
from dataclasses import dataclass

ALL_DOMAINS = ("biz", "network", "cs")

@dataclass
class EffectiveAccess:
    role: str
    domains: list[str]
    can_ask: bool
    can_manage_users: bool
    can_manage_workspace: bool

def resolve_access(*, org_role: str, member_role: str | None, member_domains: list[str] | None, is_org_admin: bool) -> EffectiveAccess:
    if is_org_admin or org_role == "org_admin":
        return EffectiveAccess("org_admin", list(ALL_DOMAINS), True, True, True)
    role = member_role or org_role
    domains = list(member_domains or [])
    return EffectiveAccess(
        role=role,
        domains=domains,
        can_ask=role in ("org_admin", "analyst"),
        can_manage_users=False,
        can_manage_workspace=False,
    )
```

`auth.py`: change token payload to `{"sub": str(user_id), "org_id": org_id, "exp": ...}`; `decode_token` returns dict or add `decode_token_payload`.

- [ ] **Step 3: Add dependency** `cryptography` already via python-jose; ensure available. Add `pymysql` to `pyproject.toml` dependencies for MySQL family.

- [ ] **Step 4: pytest + commit**

```bash
pytest tests/test_crypto.py tests/test_acl.py -v
git add apps/api/crypto.py apps/api/acl.py apps/api/auth.py apps/api/settings.py pyproject.toml tests/test_crypto.py tests/test_acl.py
git commit -m "feat: add secret crypto JWT claims and ACL helper"
```

---

### Task 3: Auth routes — login against ti_user + /auth/me

**Files:**
- Create: `apps/api/routes_auth.py`
- Modify: `apps/api/main.py`, `apps/api/deps.py`, `apps/api/schemas.py`
- Create: `tests/test_auth_users.py`
- Update existing tests that login with env-only demo

- [ ] **Step 1: Failing test** with TestClient + sqlite override

```python
def test_login_demo_and_me(client_with_seed):
    r = client_with_seed.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client_with_seed.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "demo"
    assert body["org_role"] == "org_admin"
    assert len(body["workspaces"]) >= 1
```

Provide `client_with_seed` fixture in `tests/conftest.py` if missing: override `get_session`, run `init_db` + `seed_tenant_bootstrap`.

- [ ] **Step 2: Implement login** — verify bcrypt hash; disabled users 401; issue JWT with user id.

`/auth/me` returns: `id, username, display_name, org_id, org_name, org_role, workspaces: [{id, name, role, domains}]`.

- [ ] **Step 3: Change `get_current_user`** to return `TiUser` (or a `CurrentUser` dataclass with id/org_id/org_role). Update all route type hints that currently expect `str` — keep a thin `get_current_username` only if needed for minimal churn; prefer updating to `TiUser`.

- [ ] **Step 4: Fix broken tests** (`test_api_ask`, `test_sessions`, `test_admin_crud`, `test_health`) to seed tenant + login via `/auth/login`.

- [ ] **Step 5: commit** `feat: authenticate against ti_user and expose /auth/me`

---

### Task 4: Workspaces + members + admin users APIs

**Files:**
- Create: `apps/api/routes_workspaces.py`, `apps/api/routes_users.py`
- Modify: `apps/api/main.py`, `apps/api/schemas.py`
- Create: `tests/test_workspaces.py`

- [ ] **Step 1: Tests**

```python
def test_org_admin_creates_workspace_and_adds_member(client_admin, analyst_user_id):
    r = client_admin.post("/workspaces", json={"name": "网络专项"})
    assert r.status_code == 200
    ws_id = r.json()["id"]
    m = client_admin.post(
        f"/workspaces/{ws_id}/members",
        json={"user_id": analyst_user_id, "role": "analyst", "domains": ["network"]},
    )
    assert m.status_code == 200

def test_non_member_forbidden(client_analyst_other_ws):
    r = client_analyst_other_ws.get("/sessions", headers={"X-Workspace-Id": "999"})
    assert r.status_code == 403
```

- [ ] **Step 2: Implement routes**

- `GET /workspaces` — org_admin: all org workspaces; else: memberships only  
- `POST /workspaces` — org_admin; auto-add creator as member org_admin all domains  
- `PATCH /workspaces/{id}` — archive (`status=archived`) org_admin  
- `GET/POST/PATCH/DELETE /workspaces/{id}/members` — org_admin  
- `GET/POST/PATCH /admin/users` — org_admin; hash passwords; never return hash  

- [ ] **Step 3: `deps.require_workspace`**

```python
def require_workspace(
    x_workspace_id: int = Header(..., alias="X-Workspace-Id"),
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> tuple[TiWorkspace, EffectiveAccess]:
    ...
```

Raise 403 if not org_admin and not member; archived workspaces reject writes.

- [ ] **Step 4: pytest + commit** `feat: add workspace member and user admin APIs`

---

### Task 5: Datasource catalog + connection factory (P0 URL map)

**Files:**
- Create: `apps/api/db_types.py`, `apps/engine/connectors.py`, `apps/api/routes_datasources.py`
- Create: `tests/test_multi_db_urls.py`, `tests/test_datasources.py`

- [ ] **Step 1: URL mapping test**

```python
from apps.api.db_types import PROTOCOL_FAMILY, build_sqlalchemy_url, is_p0, is_p1

def test_p0_families():
    assert PROTOCOL_FAMILY["hive"] == "hive"
    assert PROTOCOL_FAMILY["kingbase"] == "postgres"
    assert PROTOCOL_FAMILY["dameng"] == "dm"
    assert is_p0("oceanbase_mysql") and is_p1("gbase")

def test_build_mysql_url():
    url = build_sqlalchemy_url(
        db_type="mysql", host="h", port=3306, database="d", username="u", password="p"
    )
    assert url.startswith("mysql+pymysql://")
```

Implement `PROTOCOL_FAMILY` dict for all P0 types; P1 set `{"gbase","shentong","polardb","tdsql"}`.

`build_sqlalchemy_url`:

| family | URL scheme |
|---|---|
| postgres | `postgresql+psycopg://` |
| mysql | `mysql+pymysql://` |
| mssql | `mssql+pyodbc://` (Driver=ODBC Driver 18; TrustServerCertificate optional in extra_json) |
| hive | `hive://` (SQLAlchemy hive dialect if installed) or document jaydebeapi fallback returning a thin Engine wrapper |
| dm | `dm+dmPython://` when available |

For tests without drivers: `build_sqlalchemy_url` still returns string; `test_connection` may skip if driver missing (`pytest.importorskip`).

- [ ] **Step 2: Datasource API tests** — create DS, password not in GET body, set default uniqueness, reject P1 as default with 400.

- [ ] **Step 3: Implement routes** under `/admin/datasources` with `require_workspace`; encrypt password on write; `POST /{id}/test` calls `connectors.test_connection` updating `last_ok_at`/`last_error`.

- [ ] **Step 4: commit** `feat: add multi-db datasource registry and connectors`

---

### Task 6: Wire Ask + sessions/admin to workspace + datasource

**Files:**
- Modify: `apps/api/routes_sessions.py`, `apps/api/routes_admin.py`, `apps/api/deps.py`, `apps/engine/ask.py`, `apps/engine/sql_guard.py`
- Modify: `tests/test_sessions.py`, `tests/test_admin_crud.py`
- Create: `tests/test_ask_datasource_binding.py`

- [ ] **Step 1: Guard dialect test**

```python
from apps.engine.sql_guard import guard_sql

def test_guard_mysql_read():
    sql = guard_sql("SELECT 1 AS x", table_whitelist=set(), dialect="mysql")
    assert "SELECT" in sql.upper()
```

Change signature to `guard_sql(sql, table_whitelist, dialect: str = "postgres")` and map family→sqlglot read: postgres/mysql/tsql/hive. Empty whitelist still allows no tables / or keep existing behavior — if whitelist empty and query has no tables (`SELECT 1`), allow.

- [ ] **Step 2: AskEngine** accept `warehouse` engine override already exists — ensure session ask does:

```python
ds = resolve_datasource(session, workspace_id, chat.datasource_id)
engine = build_engine_from_datasource(ds)
# pass dialect to guard via AskEngine
```

- [ ] **Step 3: Sessions/admin** always filter `workspace_id == current`; create sets workspace_id; terms/examples create checks `domain in access.domains` unless org_admin; ask checks `access.can_ask` else 403; viewer GET ok.

- [ ] **Step 4: Test ask uses datasource** — monkeypatch `build_engine_from_datasource` to record call; assert called with default DS id.

- [ ] **Step 5: commit** `feat: scope ask and admin APIs by workspace datasource`

---

### Task 7: Frontend API client + AppShell workspace switcher

**Files:**
- Modify: `web/src/api.ts`, `web/src/layouts/AppShell.vue`, `web/src/router/index.ts`

- [ ] **Step 1: api.ts** — store `ti_workspace_id` in localStorage; axios interceptor attach `X-Workspace-Id`; add:

```ts
export type MeResponse = {
  id: number;
  username: string;
  display_name: string;
  org_id: number;
  org_name: string;
  org_role: string;
  workspaces: Array<{ id: number; name: string; role: string; domains: string[] }>;
};

export async function fetchMe(): Promise<MeResponse> { ... }
export async function listWorkspaces() { ... }
export async function listDatasources() { ... }
// users, members, CRUD helpers mirroring admin pattern
```

On login success, call `fetchMe()`, set default workspace id to first workspace.

- [ ] **Step 2: AppShell** — load me on mount; select for workspace switch (reload child via `:key="workspaceId"` on RouterView); show org name + role; enable nav links 数据源/工作空间/用户; remove 即将推出 block.

- [ ] **Step 3: Router** add:

```ts
{ path: "datasources", name: "datasources", component: DatasourcesView },
{ path: "workspaces", name: "workspaces", component: WorkspacesView },
{ path: "users", name: "users", component: UsersView },
```

- [ ] **Step 4: Manual smoke** — `npm run build` in `web/`

- [ ] **Step 5: commit** `feat: add workspace switcher and tenant API client`

---

### Task 8: Admin pages — Datasources / Workspaces / Users

**Files:**
- Create: `web/src/views/admin/DatasourcesView.vue`, `WorkspacesView.vue`, `UsersView.vue`
- Reuse: `admin-shared.css`

- [ ] **Step 1: DatasourcesView** — table columns: name, db_type, host, database, is_default, last_ok; form fields per model; db_type select lists P0 enabled + P1 disabled options; buttons 测连 / 设默认 / 删除; password input write-only placeholder `••••`.

- [ ] **Step 2: WorkspacesView** — list spaces; create; archive; row opens member drawer (user select, role, domain checkboxes biz/network/cs).

- [ ] **Step 3: UsersView** — org users table; create/edit username password display_name org_role enabled; hide from non-org_admin (route still 403 from API).

- [ ] **Step 4: `npm run build` + commit `feat: add datasource workspace and user admin pages`

---

### Task 9: ChatView gates + domain filter + empty datasource

**Files:**
- Modify: `web/src/views/ChatView.vue`, `web/src/layouts/AppShell.vue` (pass me via provide/inject or small store module)

- [ ] **Step 1:** `provide('me', meRef)` in AppShell; ChatView `inject`. Filter domain select to `me.workspaces[current].domains` (org_admin → all three).

- [ ] **Step 2:** If role `viewer`: hide 新建对话 + composer; show banner「只读账号，仅可浏览历史」。

- [ ] **Step 3:** On load datasources; if none default, show empty state CTA linking to `/app/datasources`.

- [ ] **Step 4: commit `feat: gate chat UI by role domain and datasource`

---

### Task 10: Multi-DB smoke matrix + docs + acceptance

**Files:**
- Create: `docs/superpowers/plans/phase1b-db-verification-matrix.md` (or section in README)
- Modify: `README.md`
- Ensure: `tests/test_multi_db_urls.py` covers every P0 `db_type` key
- Optional: `tests/test_connectors_postgres_mysql.py` with skip if no DSN env

- [ ] **Step 1: Verification matrix doc** — table of P0 types: unit URL ✓, local docker ✓/manual, driver package name.

- [ ] **Step 2: README** — document `X-Workspace-Id`, demo users, how to add MySQL datasource, Hive notes (JDBC URL in `extra_json`).

- [ ] **Step 3: Full pytest**

```bash
pytest -v
```

Expected: all green (skips only for missing optional drivers).

- [ ] **Step 4: Docker rebuild smoke** — login demo, switch workspace UI, ask ARPU on default PG.

- [ ] **Step 5: commit** `docs: phase1b acceptance notes and db verification matrix`

---

### Task 11: Spec checklist sign-off

- [ ] **Step 1:** Walk spec §7 acceptance 1–9; tick in PR description.

- [ ] **Step 2:** Confirm no SQLBot paths in diff (`git grep -i sqlbot` empty).

- [ ] **Step 3:** Open PR to main when user requests (do not push unless asked).

---

## Self-review (plan vs spec)

| Spec item | Task |
|---|---|
| Org/workspace/members | 1, 4 |
| Three roles + domain ACL | 2, 4, 6, 9 |
| Switchable datasource + Ask | 5, 6 |
| Multi-DB P0 + Hive + domestic | 5, 10 |
| P1 placeholder | 5, 8 |
| `/auth/me`, JWT user_id | 3 |
| Frontend pages + switcher | 7, 8, 9 |
| Seed demo + backfill | 1 |
| pytest coverage | 1–6, 10 |
| Non-goals excluded | No RLS/SSO/federated/write SQL tasks |

**Type names locked:** `EffectiveAccess`, `TiOrg`, `TiWorkspace`, `TiUser`, `TiWorkspaceMember`, `TiDatasource`, `PROTOCOL_FAMILY`, `build_sqlalchemy_url`, `require_workspace`, header `X-Workspace-Id`.

---

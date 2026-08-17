# 元景.智数

运营商智能问数：自然语言提问 → 受控 SQL → 表格 / 图表 / 叙述，覆盖经营、网络、客服三个业务域。

## What it is

- **产品名**：元景.智数  
- **仓库名**：telecom-insight  
- FastAPI 问数 API + Industry Packs（YAML）+ SQL Guard（只读 / 表白名单）+ Vue 3 ChatBI 门户  
- 演示数据落在 PostgreSQL schema：`biz` / `network` / `cs`  
- 应用表（会话、模型、术语、示例）使用 `ti_*` 前缀

## Phase 1a

- **ChatBI shell**：登录后进入 `/app` AppShell（侧栏导航 + 工作区）
- **多会话问数**：创建 / 切换会话，`POST /sessions/{id}/ask` 持久化用户与助手消息（含 SQL / 图表 / 叙述 / steps）
- **管理页**：`/app/models`、`/app/terms`、`/app/examples` — AI 模型、业务术语、SQL 示例 CRUD
- **演示登录**：`demo` / `demo123`

## Phase 1b

- **组织 / 工作空间 / 成员**：租户边界；种子组织「演示运营商」+ 默认工作空间
- **角色**：`org_admin` / `analyst` / `viewer`；域权限 `biz` / `network` / `cs`
- **请求头**：需空间上下文的 API 携带 `Authorization` + **`X-Workspace-Id`**
- **数据源**：可切换执行库；Ask 打到会话绑定源或空间默认源
- **演示登录不变**：`demo` / `demo123`（`org_admin`，默认空间全开）
- **白标外观**：`org_admin` 侧栏「外观」可改产品名、副标题、预设色板、Logo/favicon；`analyst` / `viewer` 无写入口
- **多库 P0**：Postgres / MySQL / SQL Server / Hive / OpenGauss / GaussDB / OceanBase(MySQL) / TiDB / Kingbase / Dameng — 验证矩阵见 [phase1b-db-verification-matrix.md](docs/superpowers/plans/phase1b-db-verification-matrix.md)
- **可选驱动**：Hive JDBC / Dameng `dmPython` 等非默认依赖；无驱动时 CI 仍跑 URL 单元测试，测连可跳过

## Row-level security (RLS)

- **成员行权限**：工作空间成员可配置 `in` / `eq` 策略（如 `biz.sub_month.region`）；Ask 在 SQL Guard 之后改写，Prompt 注入过滤提示
- **组织旁路开关**：`org_admin` 可开关 `rls_admin_bypass`（默认开）— 开启时组织管理员提问跳过行级过滤
- **演示账号**：`analyst1` / `analyst123`（种子策略：区域 ∈ `华东`）；`demo` / `demo123` 仍为 `org_admin`

## Schema Catalog & field ACL

- **Catalog 服务**：外挂 FastAPI（Compose 服务 `catalog`），默认 **http://localhost:8001**；主 API 经 `TI_CATALOG_BASE_URL` 调用（Compose 内为 `http://catalog:8001`）
- **授权流程**（数据源页，仅 `org_admin`）：「刷新结构」探测并快照表/列 →「字段授权」勾选工作空间可用表与列并保存
- **Ask 生效规则**：表白名单与列允许集来自 Catalog `effective`（Pack `table_whitelist` 不再作为真相）；**空授权拒绝 Ask**；未授权列拒绝（不遮罩）
- **演示种子**：启动时对演示默认源预授权 `biz.sub_month` / `biz.channel_day` 等核心列，保证 `demo` 开箱可问

## Clean-room note

本项目为独立 clean-room 实现，**不是** SQLBot 的 fork、拷贝或衍生作品。架构与代码均为本仓库原创。

## Quick start (Docker Compose)

```bash
docker compose -f docker/docker-compose.yml up --build
```

| Service | URL |
|---------|-----|
| Web | http://localhost:8080 |
| API | http://localhost:8000 |
| Catalog | http://localhost:8001 |
| Postgres | localhost:5432 |

Demo login: **demo** / **demo123**（`org_admin`）；RLS 演示：**analyst1** / **analyst123**（华东行权限）

Compose volumes: `pgdata`（库数据）、`branding_data`（组织 Logo/favicon 上传，挂到 API 的 `TI_BRANDING_DATA_DIR`）。

首次启动后如需灌数（视 compose / 镜像是否已 seed）：

```bash
python scripts/seed_all.py
```

## Domains

| id | 名称 |
|----|------|
| `biz` | 经营分析 |
| `network` | 网络运维 |
| `cs` | 客户服务 |

每个域推荐问 ≥ 8 条；ChatBI 工作区可切换域并一键提问。

## Environment variables

Copy `.env.example` and adjust. Prefix is `TI_`:

| Variable | Meaning |
|----------|---------|
| `TI_JWT_SECRET` | JWT signing secret |
| `TI_DEMO_USERNAME` / `TI_DEMO_PASSWORD` | Demo login (default demo / demo123) |
| `TI_DATABASE_URL` | SQLAlchemy URL (Postgres or SQLite for tests) |
| `TI_CATALOG_BASE_URL` | Catalog service base URL (default `http://127.0.0.1:8001`) |
| `TI_CATALOG_DATABASE_URL` | Catalog DB URL (Compose: same Postgres; SQLite OK for Catalog unit tests) |
| `TI_PACKS_ROOT` | Industry packs directory (default `packs`) |
| `TI_BRANDING_DATA_DIR` | Org logo/favicon upload dir (default `data/branding`; Compose volume `branding_data`) |
| `TI_LLM_API_KEY` | Optional; empty → demo FakeLLM from pack examples |
| `TI_LLM_BASE_URL` | Optional OpenAI-compatible base URL |
| `TI_LLM_MODEL` | Model name (default `gpt-4o-mini`) |

## Local development

```bash
# API / engine tests
python -m pip install -e ".[dev]"
python -m pytest -v

# Web
cd web && npm install && npm run dev
```

## Acceptance check

Against a running API (default `http://localhost:8000`):

```bash
python scripts/acceptance_check.py
# optional: also POST /sessions/{id}/ask with a recommended question
TI_RUN_ASK=1 python scripts/acceptance_check.py
# no server: in-process FastAPI TestClient
TI_USE_TESTCLIENT=1 python scripts/acceptance_check.py
```

Checks: `/health`, login, `/domains`, recommended count ≥ 8 for `biz` / `network` / `cs`, create session, authenticated list of `/admin/models` / `/admin/terms` / `/admin/examples`, and (when `TI_RUN_ASK=1`) session ask. Exits non-zero on failure. If the API is not up, the script fails by design — start compose first (or use `TI_USE_TESTCLIENT=1`).

## License

Apache-2.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

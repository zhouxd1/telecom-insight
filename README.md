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
| Postgres | localhost:5432 |

Demo login: **demo** / **demo123**

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
| `TI_PACKS_ROOT` | Industry packs directory (default `packs`) |
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

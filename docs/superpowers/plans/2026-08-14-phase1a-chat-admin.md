# Phase 1a ChatBI Workspace + Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deliver 元景.智数 Phase 1a — ChatBI multi-session workspace plus admin CRUD for AI models, terminology, and SQL examples (clean-room; no SQLBot code).

**Architecture:** Postgres `ti_*` app tables; FastAPI session/admin routes; AskEngine merges DB terms/examples with Packs and uses enabled `ti_ai_model`; Vue AppShell with ChatWorkspace + three admin pages.

**Tech Stack:** Existing FastAPI/SQLModel/Vue3/ECharts; SQLAlchemy models; JWT auth unchanged.

**Spec:** `docs/superpowers/specs/2026-08-14-phase1a-chat-admin-design.md`

**Clean-room:** Never copy from SQLBot-main.

---

## File map

| Path | Responsibility |
|---|---|
| `apps/api/db.py` | Engine/session for app DB (TI_DATABASE_URL) |
| `apps/api/models_db.py` | SQLModel tables ti_* |
| `apps/api/init_db.py` | create_all + optional pack seed into terms/examples |
| `apps/api/routes_sessions.py` | Session/message/ask routes |
| `apps/api/routes_admin.py` | Models/terms/examples CRUD |
| `apps/api/schemas.py` | Extend Pydantic schemas |
| `apps/api/main.py` | Include routers; startup init_db |
| `apps/engine/ask.py` | Accept optional extra terms/examples; build steps in response helper |
| `apps/api/deps.py` | Build LLM from DB model; merge terms/examples |
| `web/src/layouts/AppShell.vue` | Shell + nav |
| `web/src/views/ChatWorkspace.vue` | Sessions + thread + composer |
| `web/src/views/admin/*.vue` | Models, Terms, Examples |
| `web/src/router/index.ts` | /app/* routes |
| `tests/test_sessions.py` | Session ask persistence |
| `tests/test_admin_crud.py` | Admin CRUD |

---

### Task 1: App DB models + init

**Files:** Create `apps/api/db.py`, `apps/api/models_db.py`, `apps/api/init_db.py`; Test `tests/test_init_db.py`

- [ ] **Step 1: Failing test** — `init_db(engine)` creates tables; can insert `TiChatSession`

- [ ] **Step 2: Implement SQLModel models**

Tables: `TiChatSession`, `TiChatMessage`, `TiAiModel`, `TiTerm`, `TiSqlExample` per spec field list. Use `sqlite://` in tests.

- [ ] **Step 3: `init_db(engine)`** calls `SQLModel.metadata.create_all`

- [ ] **Step 4: pytest pass + commit** `feat: add app DB models and init`

---

### Task 2: Admin CRUD APIs

**Files:** `apps/api/routes_admin.py`, extend `schemas.py`, wire `main.py`; `tests/test_admin_crud.py`

- [ ] **Step 1: Tests** for models/terms/examples create+list with auth TestClient; unique enabled model flips others off

- [ ] **Step 2: Implement routers** under `/admin/models`, `/admin/terms`, `/admin/examples`

- [ ] **Step 3: Model test endpoint** returns `{ ok: true }` if Fake or simple HTTP ping skipped when no key

- [ ] **Step 4: commit** `feat: add admin CRUD for models terms examples`

---

### Task 3: Sessions + session ask

**Files:** `apps/api/routes_sessions.py`; `tests/test_sessions.py`

- [ ] **Step 1: Tests** create session, ask with monkeypatched engine, messages persisted with assistant content_json containing sql/chart keys

- [ ] **Step 2: Implement** GET/POST/PATCH/DELETE sessions; GET messages; POST ask  
  Ask flow: save user msg → `AskEngine.ask` → build steps array → save assistant msg → return card

- [ ] **Step 3: commit** `feat: add chat sessions and session ask API`

---

### Task 4: Wire AskEngine to DB context

**Files:** Modify `apps/engine/ask.py`, `apps/api/deps.py`

- [ ] **Step 1: Extend AskEngine** to accept `extra_terms: list[Term]`, `extra_examples: list[Example]` merged with pack

- [ ] **Step 2: deps.get_ask_engine** loads enabled TiAiModel; loads TiTerm/TiSqlExample by domain when asking (pass in ask route)

- [ ] **Step 3: Test** that DB term appears in merged terminology string used by FakeLLM path (unit test on merge helper)

- [ ] **Step 4: commit** `feat: merge DB terms examples and model into ask`

---

### Task 5: Seed pack → DB on startup

**Files:** `apps/api/init_db.py`, `main.py` lifespan

- [ ] **Step 1:** If terms empty for domain, import from pack YAML (idempotent by term text)

- [ ] **Step 2:** Same for examples

- [ ] **Step 3:** commit `feat: seed terms and examples from packs on startup`

---

### Task 6: Vue AppShell + router

**Files:** `web/src/layouts/AppShell.vue`, update `router`, `App.vue`, styles

- [ ] **Step 1:** Routes `/app/chat`, `/app/models`, `/app/terms`, `/app/examples` behind auth; login redirect

- [ ] **Step 2:** Shell: logo 元景.智数, sidebar nav, outlet; 1b items disabled

- [ ] **Step 3:** `npm run build` + commit `feat: add app shell and admin routes`

---

### Task 7: ChatWorkspace ChatBI UI

**Files:** `web/src/views/ChatWorkspace.vue`, components `SessionList.vue`, `MessageThread.vue`, `AssistantCard.vue`, `Composer.vue`; update `api.ts`

- [ ] **Step 1:** Wire sessions API; left list + new chat

- [ ] **Step 2:** Thread bubbles; AssistantCard shows steps/sql/table/chart/narrative

- [ ] **Step 3:** Composer + recommended; polished layout (teal/ink, not form-page); motion on step reveal

- [ ] **Step 4:** build + commit `feat: rebuild ChatBI workspace UI`

---

### Task 8: Admin pages UI

**Files:** `web/src/views/admin/ModelsView.vue`, `TermsView.vue`, `ExamplesView.vue`

- [ ] **Step 1:** Each page list + create/edit dialog + delete

- [ ] **Step 2:** Domain filter on terms/examples

- [ ] **Step 3:** build + commit `feat: add admin UI for models terms examples`

---

### Task 9: Acceptance + docs

- [ ] **Step 1:** Extend `scripts/acceptance_check.py` for sessions ask + admin list

- [ ] **Step 2:** Update README Phase 1a section

- [ ] **Step 3:** Full `pytest` + `npm run build`

- [ ] **Step 4:** commit `docs: phase1a acceptance and readme`

---

## Spec coverage

| Spec item | Task |
|---|---|
| ti_* tables | 1 |
| Admin CRUD APIs | 2 |
| Sessions + ask persist | 3 |
| DB merge into Ask | 4–5 |
| AppShell + ChatBI UI | 6–7 |
| Admin UI | 8 |
| Acceptance | 9 |
| 1b out of scope | — |

## Execution

After plan saved: use subagent-driven-development on `feature/phase1a` worktree.

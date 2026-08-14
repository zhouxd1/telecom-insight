# TelecomInsight P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a clean-room operator ChatBI MVP: three domain packs, synthetic Postgres, guarded Text-to-SQL ask pipeline, and a Vue portal that returns table + chart + narrative.

**Architecture:** FastAPI API fronts a LangChain-orchestrated Ask Engine. Domain Industry Packs (YAML) supply terminology, metrics, schema text, few-shots, and recommended questions. SQL Guard enforces read-only + domain table whitelist before execution against synthetic schemas `biz` / `network` / `cs`. Vue 3 portal switches domains and renders results with ECharts.

**Tech Stack:** Python 3.11, FastAPI, SQLModel, LangChain, OpenAI-compatible LLM API, PostgreSQL, Vue 3 + Vite + TypeScript + ECharts, Docker Compose, pytest, Apache-2.0.

**Spec:** `docs/superpowers/specs/2026-08-14-telecom-insight-design.md`

**Clean-room rule:** Never open or copy from `SQLBot-main`. All prompts, UI, and schema are original.

---

## File map (create)

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Backend deps + pytest entry |
| `apps/__init__.py` | Package root |
| `apps/packs/models.py` | Pack dataclasses / Pydantic models |
| `apps/packs/loader.py` | Load YAML pack from disk |
| `apps/engine/sql_guard.py` | Read-only SQL validation + table whitelist |
| `apps/engine/schema_rag.py` | Keyword (+ optional embedding) schema retrieval |
| `apps/engine/executor.py` | Run SELECT with row/timeout limits |
| `apps/engine/chart.py` | Infer simple ECharts option from result columns |
| `apps/engine/clarify.py` | Detect missing time/region/metric slots |
| `apps/engine/llm.py` | OpenAI-compatible chat wrapper (injectable) |
| `apps/engine/ask.py` | Full ask pipeline orchestration |
| `apps/engine/audit.py` | Persist ask audit records |
| `apps/api/auth.py` | Demo JWT login |
| `apps/api/schemas.py` | Request/response models |
| `apps/api/main.py` | FastAPI app + routes |
| `packs/biz/**` | Business domain pack + seed |
| `packs/network/**` | Network domain pack + seed |
| `packs/cs/**` | Customer-service domain pack + seed |
| `docker/docker-compose.yml` | api + web + postgres |
| `docker/api.Dockerfile` | API image |
| `docker/web.Dockerfile` | Web image |
| `docker/init-db.sql` | Create schemas + run seeds hook |
| `web/**` | Vue portal |
| `LICENSE` | Apache-2.0 |
| `THIRD_PARTY_NOTICES.md` | Dependency license list |
| `tests/**` | Unit/integration tests |

---

### Task 1: Python project skeleton + failing health test

**Files:**
- Create: `pyproject.toml`
- Create: `apps/__init__.py`
- Create: `apps/api/__init__.py`
- Create: `apps/api/main.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "telecom-insight"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:\currse_workpalce\telecom-insight && python -m pytest tests/test_health.py -v`  
Expected: FAIL (module/app missing or `/health` missing)

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "telecom-insight"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlmodel>=0.0.22",
  "psycopg[binary]>=3.2.0",
  "pyyaml>=6.0.2",
  "pydantic-settings>=2.4.0",
  "python-jose[cryptography]>=3.3.0",
  "passlib[bcrypt]>=1.7.4",
  "httpx>=0.27.0",
  "langchain>=0.3.0",
  "langchain-openai>=0.2.0",
  "sqlglot>=25.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```python
# apps/__init__.py
# apps/api/__init__.py

# apps/api/main.py
from fastapi import FastAPI

app = FastAPI(title="TelecomInsight", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "telecom-insight"}
```

- [ ] **Step 4: Install deps and run test**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_health.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml apps tests/test_health.py
git commit -m "chore: scaffold FastAPI app with health endpoint"
```

---

### Task 2: Industry Pack models + loader

**Files:**
- Create: `apps/packs/__init__.py`
- Create: `apps/packs/models.py`
- Create: `apps/packs/loader.py`
- Create: `tests/fixtures/mini_pack/manifest.yaml`
- Create: `tests/fixtures/mini_pack/terminology.yaml`
- Create: `tests/fixtures/mini_pack/metrics.yaml`
- Create: `tests/fixtures/mini_pack/examples.yaml`
- Create: `tests/fixtures/mini_pack/recommended.yaml`
- Create: `tests/fixtures/mini_pack/schema/tables.md`
- Create: `tests/test_pack_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pack_loader.py
from pathlib import Path
from apps.packs.loader import load_pack

FIX = Path(__file__).parent / "fixtures" / "mini_pack"

def test_load_pack_reads_manifest_and_recommended():
    pack = load_pack(FIX)
    assert pack.domain == "mini"
    assert pack.version == "0.1.0"
    assert len(pack.recommended) >= 1
    assert "users" in pack.table_whitelist
    assert pack.terminology[0].term == "ARPU"
```

Fixture files:

```yaml
# tests/fixtures/mini_pack/manifest.yaml
domain: mini
version: 0.1.0
engine_compat: ">=0.1.0"
schemas: [mini]
tables: [users]
```

```yaml
# tests/fixtures/mini_pack/terminology.yaml
- term: ARPU
  standard: 每用户平均收入
  maps_to: users.arpu
```

```yaml
# tests/fixtures/mini_pack/metrics.yaml
- name: arpu
  label: ARPU
  description: 月均每用户收入
  dimensions: [month, region]
  sql_hint: "AVG(arpu)"
```

```yaml
# tests/fixtures/mini_pack/examples.yaml
- question: 上月ARPU是多少
  sql: "SELECT month, AVG(arpu) AS arpu FROM mini.users GROUP BY month"
```

```yaml
# tests/fixtures/mini_pack/recommended.yaml
- id: q1
  text: 上月ARPU是多少
```

```markdown
# tests/fixtures/mini_pack/schema/tables.md
## mini.users
- month: 月份
- region: 地区
- arpu: 每用户平均收入
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pack_loader.py -v`  
Expected: FAIL (`load_pack` missing)

- [ ] **Step 3: Implement models + loader**

```python
# apps/packs/models.py
from pydantic import BaseModel, Field

class Term(BaseModel):
    term: str
    standard: str
    maps_to: str | None = None

class Metric(BaseModel):
    name: str
    label: str
    description: str
    dimensions: list[str] = Field(default_factory=list)
    sql_hint: str | None = None

class Example(BaseModel):
    question: str
    sql: str

class Recommended(BaseModel):
    id: str
    text: str

class IndustryPack(BaseModel):
    domain: str
    version: str
    engine_compat: str = ">=0.1.0"
    schemas: list[str] = Field(default_factory=list)
    table_whitelist: list[str] = Field(default_factory=list)
    terminology: list[Term] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    recommended: list[Recommended] = Field(default_factory=list)
    schema_docs: str = ""
```

```python
# apps/packs/loader.py
from pathlib import Path
import yaml
from apps.packs.models import IndustryPack, Term, Metric, Example, Recommended

def _read_yaml(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_pack(pack_dir: Path) -> IndustryPack:
    pack_dir = Path(pack_dir)
    manifest = _read_yaml(pack_dir / "manifest.yaml") or {}
    schema_dir = pack_dir / "schema"
    docs = []
    if schema_dir.exists():
        for p in sorted(schema_dir.glob("*.md")):
            docs.append(p.read_text(encoding="utf-8"))
    return IndustryPack(
        domain=manifest["domain"],
        version=manifest["version"],
        engine_compat=manifest.get("engine_compat", ">=0.1.0"),
        schemas=list(manifest.get("schemas", [])),
        table_whitelist=list(manifest.get("tables", [])),
        terminology=[Term(**x) for x in (_read_yaml(pack_dir / "terminology.yaml") or [])],
        metrics=[Metric(**x) for x in (_read_yaml(pack_dir / "metrics.yaml") or [])],
        examples=[Example(**x) for x in (_read_yaml(pack_dir / "examples.yaml") or [])],
        recommended=[Recommended(**x) for x in (_read_yaml(pack_dir / "recommended.yaml") or [])],
        schema_docs="\n\n".join(docs),
    )

def load_pack_by_domain(packs_root: Path, domain: str) -> IndustryPack:
    return load_pack(Path(packs_root) / domain)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pack_loader.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/packs tests/fixtures/mini_pack tests/test_pack_loader.py
git commit -m "feat: add industry pack models and YAML loader"
```

---

### Task 3: SQL Guard (read-only + whitelist)

**Files:**
- Create: `apps/engine/__init__.py`
- Create: `apps/engine/sql_guard.py`
- Create: `tests/test_sql_guard.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sql_guard.py
import pytest
from apps.engine.sql_guard import guard_sql, SqlGuardError

WL = {"users", "orders"}

def test_allows_simple_select():
    sql = guard_sql("SELECT month, AVG(arpu) FROM users GROUP BY month", WL)
    assert "select" in sql.lower()

def test_rejects_insert():
    with pytest.raises(SqlGuardError):
        guard_sql("INSERT INTO users VALUES (1)", WL)

def test_rejects_multi_statement():
    with pytest.raises(SqlGuardError):
        guard_sql("SELECT 1; DROP TABLE users", WL)

def test_rejects_unknown_table():
    with pytest.raises(SqlGuardError):
        guard_sql("SELECT * FROM secrets", WL)

def test_allows_schema_qualified_whitelist_name():
    sql = guard_sql("SELECT * FROM biz.users", {"users"})
    assert "users" in sql.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sql_guard.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement guard**

```python
# apps/engine/sql_guard.py
import re
import sqlglot
from sqlglot import exp

class SqlGuardError(ValueError):
    pass

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE|REPLACE|ATTACH|COPY)\b",
    re.I,
)

def _base_table_name(name: str) -> str:
    return name.split(".")[-1].strip('"').lower()

def guard_sql(sql: str, table_whitelist: set[str] | list[str]) -> str:
    raw = (sql or "").strip().rstrip(";")
    if not raw:
        raise SqlGuardError("empty sql")
    if ";" in raw:
        raise SqlGuardError("multiple statements are not allowed")
    if _FORBIDDEN.search(raw):
        raise SqlGuardError("only SELECT statements are allowed")

    try:
        trees = sqlglot.parse(raw, read="postgres")
    except Exception as e:
        raise SqlGuardError(f"sql parse failed: {e}") from e
    if len(trees) != 1 or trees[0] is None:
        raise SqlGuardError("exactly one statement required")
    tree = trees[0]
    if not isinstance(tree, exp.Select):
        # WITH ... SELECT is still Select in sqlglot
        if not any(isinstance(tree, t) for t in (exp.Select, exp.Union)):
            raise SqlGuardError("only SELECT is allowed")

    allowed = {t.lower() for t in table_whitelist}
    used = set()
    for t in tree.find_all(exp.Table):
        used.add(_base_table_name(t.name))
    unknown = used - allowed
    if unknown:
        raise SqlGuardError(f"tables not in domain whitelist: {sorted(unknown)}")
    return raw
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_guard.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/engine tests/test_sql_guard.py
git commit -m "feat: add SQL guard for read-only domain whitelist"
```

---

### Task 4: Schema RAG (keyword retrieval for P0)

**Files:**
- Create: `apps/engine/schema_rag.py`
- Create: `tests/test_schema_rag.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema_rag.py
from apps.packs.models import IndustryPack, Term, Metric
from apps.engine.schema_rag import retrieve_schema_context

def test_retrieve_prefers_arpu_section():
    pack = IndustryPack(
        domain="biz",
        version="0.1.0",
        table_whitelist=["users", "channel"],
        terminology=[Term(term="ARPU", standard="每用户平均收入", maps_to="users.arpu")],
        metrics=[Metric(name="arpu", label="ARPU", description="月均收入", dimensions=["month"])],
        schema_docs="## biz.users\n- arpu: 每用户平均收入\n\n## biz.channel\n- channel_name: 渠道名\n",
    )
    ctx = retrieve_schema_context(pack, "上月ARPU是多少", top_k=1)
    assert "biz.users" in ctx
    assert "channel" not in ctx.lower() or "arpu" in ctx.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema_rag.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement keyword retriever**

```python
# apps/engine/schema_rag.py
import re
from apps.packs.models import IndustryPack

def _sections(schema_docs: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^##\s+", schema_docs)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        title, _, body = p.partition("\n")
        out.append((title.strip(), body.strip()))
    return out

def retrieve_schema_context(pack: IndustryPack, question: str, top_k: int = 3) -> str:
    q = question.lower()
    boost_terms = {t.term.lower() for t in pack.terminology} | {
        m.name.lower() for m in pack.metrics
    } | {m.label.lower() for m in pack.metrics}
    scored = []
    for title, body in _sections(pack.schema_docs):
        blob = f"{title}\n{body}".lower()
        score = 0
        for token in re.findall(r"[\w\u4e00-\u9fff]+", q):
            if token in blob:
                score += 2
        for t in boost_terms:
            if t and t in q and t in blob:
                score += 5
        scored.append((score, title, body))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [s for s in scored if s[0] > 0][:top_k] or scored[:1]
    return "\n\n".join(f"## {t}\n{b}" for _, t, b in picked)
```

Note: P0 uses keyword retrieval. Optional embedding can wrap the same interface later without changing callers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema_rag.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/engine/schema_rag.py tests/test_schema_rag.py
git commit -m "feat: add keyword schema retrieval for packs"
```

---

### Task 5: Executor + chart helper (SQLite for unit tests)

**Files:**
- Create: `apps/engine/executor.py`
- Create: `apps/engine/chart.py`
- Create: `tests/test_executor_chart.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_executor_chart.py
from sqlalchemy import create_engine, text
from apps.engine.executor import execute_select
from apps.engine.chart import build_chart_option

def test_execute_select_limits_rows(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50), ('2026-02', 60), ('2026-03', 70)"))
    rows, truncated = execute_select(eng, "SELECT month, arpu FROM users ORDER BY month", max_rows=2)
    assert len(rows) == 2
    assert truncated is True
    assert rows[0]["month"] == "2026-01"

def test_build_chart_line_for_month_metric():
    rows = [{"month": "2026-01", "arpu": 50}, {"month": "2026-02", "arpu": 60}]
    opt = build_chart_option(rows)
    assert opt["type"] == "line"
    assert opt["x"] == ["2026-01", "2026-02"]
    assert opt["series"][0]["data"] == [50, 60]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_executor_chart.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# apps/engine/executor.py
from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import Engine

def execute_select(
    engine: Engine,
    sql: str,
    *,
    max_rows: int = 200,
    timeout_seconds: int = 15,
) -> tuple[list[dict[str, Any]], bool]:
    # SQLite ignores statement_timeout; Postgres can set it via options in connect.
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text(f"SET LOCAL statement_timeout = '{int(timeout_seconds * 1000)}'"))
        result = conn.execute(text(sql))
        keys = list(result.keys())
        raw = result.fetchmany(max_rows + 1)
    truncated = len(raw) > max_rows
    raw = raw[:max_rows]
    rows = [dict(zip(keys, row)) for row in raw]
    return rows, truncated
```

```python
# apps/engine/chart.py
from typing import Any

def build_chart_option(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"type": "table", "x": [], "series": []}
    keys = list(rows[0].keys())
    x_key = keys[0]
    y_key = keys[1] if len(keys) > 1 else keys[0]
    x = [r[x_key] for r in rows]
    y = [r[y_key] for r in rows]
    chart_type = "bar" if len(rows) <= 8 else "line"
    return {
        "type": chart_type,
        "xField": x_key,
        "yField": y_key,
        "x": x,
        "series": [{"name": str(y_key), "data": y}],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_executor_chart.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/engine/executor.py apps/engine/chart.py tests/test_executor_chart.py
git commit -m "feat: add SQL executor and chart option builder"
```

---

### Task 6: Clarify helper + Ask pipeline with fake LLM

**Files:**
- Create: `apps/engine/clarify.py`
- Create: `apps/engine/llm.py`
- Create: `apps/engine/ask.py`
- Create: `apps/engine/audit.py`
- Create: `tests/test_ask_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ask_pipeline.py
from sqlalchemy import create_engine, text
from apps.packs.models import IndustryPack, Example, Recommended, Term, Metric
from apps.engine.ask import AskEngine, AskRequest
from apps.engine.llm import FakeLLM

def _pack():
    return IndustryPack(
        domain="biz",
        version="0.1.0",
        schemas=["biz"],
        table_whitelist=["users"],
        terminology=[Term(term="ARPU", standard="每用户平均收入", maps_to="users.arpu")],
        metrics=[Metric(name="arpu", label="ARPU", description="月均收入", dimensions=["month"])],
        examples=[Example(question="上月ARPU", sql="SELECT month, arpu FROM users ORDER BY month")],
        recommended=[Recommended(id="1", text="上月ARPU是多少")],
        schema_docs="## users\n- month\n- arpu\n",
    )

def test_ask_returns_table_chart_narrative(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50), ('2026-02', 60)"))
    llm = FakeLLM(sql="SELECT month, arpu FROM users ORDER BY month", narrative="ARPU 呈上升趋势。")
    engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _pack()})
    resp = engine.ask(AskRequest(domain="biz", question="2026年各月ARPU是多少"))
    assert resp.status == "ok"
    assert len(resp.rows) == 2
    assert resp.chart["type"] in {"line", "bar"}
    assert "ARPU" in resp.narrative or "上升" in resp.narrative
    assert resp.sql.lower().startswith("select")

def test_ask_blocks_write_sql(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
    llm = FakeLLM(sql="DELETE FROM users", narrative="x")
    engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _pack()})
    resp = engine.ask(AskRequest(domain="biz", question="删掉用户"))
    assert resp.status == "error"
    assert "安全" in resp.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ask_pipeline.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement clarify, llm, audit, ask**

```python
# apps/engine/clarify.py
import re

_TIME = re.compile(r"(年|月|日|周|季度|上月|本月|今年|去年|\d{4})")
_REGION = re.compile(r"(省|市|区|地区|全国|本地网)")

def needs_clarification(question: str, metric_labels: list[str]) -> str | None:
    q = question.strip()
    if not q:
        return "请输入要查询的问题。"
    has_metric = any(m.lower() in q.lower() for m in metric_labels if m)
    # Only clarify when question is extremely vague (no metric-like token and very short)
    if len(q) < 4 and not has_metric:
        return "请补充要查询的指标，例如 ARPU、投诉量或流量。"
    return None
```

```python
# apps/engine/llm.py
from typing import Protocol

class LLMClient(Protocol):
    def generate_sql(self, *, question: str, schema_ctx: str, examples: list[tuple[str, str]], terminology: str) -> str: ...
    def narrate(self, *, question: str, sql: str, rows_preview: list[dict]) -> str: ...

class FakeLLM:
    def __init__(self, sql: str, narrative: str):
        self.sql = sql
        self.narrative = narrative
    def generate_sql(self, **kwargs) -> str:
        return self.sql
    def narrate(self, **kwargs) -> str:
        return self.narrative

class OpenAICompatibleLLM:
    """Real client; used in API runtime. Keep prompts original (not copied from SQLBot)."""
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        from langchain_openai import ChatOpenAI
        self._llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0)

    def generate_sql(self, *, question: str, schema_ctx: str, examples: list[tuple[str, str]], terminology: str) -> str:
        demo = "\n".join(f"Q: {q}\nSQL: {s}" for q, s in examples[:5])
        prompt = (
            "你是运营商数据分析助手。只输出一条 PostgreSQL SELECT 语句，不要解释。\n"
            f"术语:\n{terminology}\n\n可用表结构:\n{schema_ctx}\n\n示例:\n{demo}\n\n用户问题: {question}\nSQL:"
        )
        msg = self._llm.invoke(prompt)
        text = msg.content if hasattr(msg, "content") else str(msg)
        return text.strip().strip("`").removeprefix("sql").strip()

    def narrate(self, *, question: str, sql: str, rows_preview: list[dict]) -> str:
        prompt = (
            "根据查询结果用一句中文总结业务结论，不要编造数字以外的事实。\n"
            f"问题: {question}\nSQL: {sql}\n结果预览: {rows_preview[:5]}\n结论:"
        )
        msg = self._llm.invoke(prompt)
        return (msg.content if hasattr(msg, "content") else str(msg)).strip()
```

```python
# apps/engine/audit.py
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class AuditRecord:
    domain: str
    question: str
    sql: str | None
    ok: bool
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class InMemoryAuditLog:
    def __init__(self):
        self.records: list[AuditRecord] = []
    def write(self, rec: AuditRecord) -> None:
        self.records.append(rec)
```

```python
# apps/engine/ask.py
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy.engine import Engine
from apps.packs.models import IndustryPack
from apps.engine.schema_rag import retrieve_schema_context
from apps.engine.sql_guard import guard_sql, SqlGuardError
from apps.engine.executor import execute_select
from apps.engine.chart import build_chart_option
from apps.engine.clarify import needs_clarification
from apps.engine.audit import AuditRecord, InMemoryAuditLog
from apps.engine.llm import LLMClient

@dataclass
class AskRequest:
    domain: str
    question: str

@dataclass
class AskResponse:
    status: str  # ok | clarify | error
    message: str = ""
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    chart: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""

class AskEngine:
    def __init__(
        self,
        *,
        warehouse: Engine,
        llm: LLMClient,
        packs_by_domain: dict[str, IndustryPack],
        audit: InMemoryAuditLog | None = None,
        max_rows: int = 200,
    ):
        self.warehouse = warehouse
        self.llm = llm
        self.packs = packs_by_domain
        self.audit = audit or InMemoryAuditLog()
        self.max_rows = max_rows

    def ask(self, req: AskRequest) -> AskResponse:
        pack = self.packs.get(req.domain)
        if not pack:
            return AskResponse(status="error", message=f"未知业务域: {req.domain}")
        clarify = needs_clarification(req.question, [m.label for m in pack.metrics] + [t.term for t in pack.terminology])
        if clarify:
            self.audit.write(AuditRecord(req.domain, req.question, None, False, clarify))
            return AskResponse(status="clarify", message=clarify)

        schema_ctx = retrieve_schema_context(pack, req.question)
        terminology = "\n".join(f"{t.term}=>{t.standard}" for t in pack.terminology)
        examples = [(e.question, e.sql) for e in pack.examples]
        try:
            sql = self.llm.generate_sql(
                question=req.question,
                schema_ctx=schema_ctx,
                examples=examples,
                terminology=terminology,
            )
            sql = guard_sql(sql, set(pack.table_whitelist))
            rows, truncated = execute_select(self.warehouse, sql, max_rows=self.max_rows)
            narrative = self.llm.narrate(question=req.question, sql=sql, rows_preview=rows)
            chart = build_chart_option(rows)
            msg = "结果已截断，请缩小时间范围或维度。" if truncated else ""
            self.audit.write(AuditRecord(req.domain, req.question, sql, True, msg))
            return AskResponse(
                status="ok",
                message=msg,
                sql=sql,
                rows=rows,
                truncated=truncated,
                chart=chart,
                narrative=narrative,
            )
        except SqlGuardError:
            msg = "无法安全执行该查询，请换一种问法（仅支持只读分析）。"
            self.audit.write(AuditRecord(req.domain, req.question, None, False, msg))
            return AskResponse(status="error", message=msg)
        except Exception:
            msg = "查询执行失败，请稍后重试或缩小范围。"
            self.audit.write(AuditRecord(req.domain, req.question, None, False, msg))
            return AskResponse(status="error", message=msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ask_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/engine tests/test_ask_pipeline.py
git commit -m "feat: add ask pipeline with guard, clarify, and audit"
```

---

### Task 7: Settings, JWT auth, API routes

**Files:**
- Create: `apps/api/settings.py`
- Create: `apps/api/auth.py`
- Create: `apps/api/schemas.py`
- Create: `apps/api/deps.py`
- Modify: `apps/api/main.py`
- Create: `tests/test_api_ask.py`

- [ ] **Step 1: Write the failing API test**

```python
# tests/test_api_ask.py
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_login_and_list_domains():
    r = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = client.get("/domains", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    domains = {d["id"] for d in r2.json()}
    assert {"biz", "network", "cs"} <= domains
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_ask.py::test_login_and_list_domains -v`  
Expected: FAIL (routes missing)

- [ ] **Step 3: Implement auth + routes (wire engine lazily)**

```python
# apps/api/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret-change-me"
    demo_username: str = "demo"
    demo_password: str = "demo123"
    packs_root: str = "packs"
    database_url: str = "sqlite://"  # overridden in compose to Postgres
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    class Config:
        env_prefix = "TI_"

settings = Settings()
```

```python
# apps/api/auth.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status
from apps.api.settings import settings

ALGORITHM = "HS256"

def create_access_token(sub: str) -> str:
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)

def decode_token(token: str) -> str:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return str(data["sub"])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from e
```

```python
# apps/api/schemas.py
from pydantic import BaseModel
from typing import Any

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DomainInfo(BaseModel):
    id: str
    name: str
    version: str

class AskBody(BaseModel):
    domain: str
    question: str

class AskApiResponse(BaseModel):
    status: str
    message: str = ""
    sql: str | None = None
    rows: list[dict[str, Any]] = []
    truncated: bool = False
    chart: dict[str, Any] = {}
    narrative: str = ""
```

Implement `apps/api/deps.py` to build/cached `AskEngine` from settings (load all packs under `packs/`, create SQLAlchemy engine from `database_url`, use `FakeLLM` when `TI_LLM_API_KEY` empty and map recommended examples; use `OpenAICompatibleLLM` when key present).

Update `apps/api/main.py` with routes: `POST /auth/login`, `GET /domains`, `GET /domains/{id}/recommended`, `POST /ask`, keep `/health` public. Protect non-health routes with `Authorization: Bearer`.

Domain display names: `biz=经营分析`, `network=网络运维`, `cs=客户服务`.

- [ ] **Step 4: Expand API test for ask with FakeLLM path**

Add test that seeds sqlite, monkeypatches deps to use in-memory pack+db, posts `/ask`, asserts `status==ok` and chart present.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_api_ask.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api tests/test_api_ask.py
git commit -m "feat: add JWT auth and ask/domain API routes"
```

---

### Task 8: Real industry packs (biz / network / cs) + seeds

**Files:**
- Create full trees under `packs/biz`, `packs/network`, `packs/cs` per spec (manifest, terminology, metrics, schema/*.md, examples, recommended ≥8 each, `seed/001_schema.sql`, `seed/002_data.sql`)
- Create: `tests/test_packs_content.py`

- [ ] **Step 1: Write content contract test**

```python
# tests/test_packs_content.py
from pathlib import Path
from apps.packs.loader import load_pack

ROOT = Path(__file__).resolve().parents[1] / "packs"

def test_three_domains_have_enough_recommended():
    for domain in ("biz", "network", "cs"):
        pack = load_pack(ROOT / domain)
        assert len(pack.recommended) >= 8
        assert len(pack.examples) >= 5
        assert len(pack.table_whitelist) >= 1
        assert pack.schema_docs.strip()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_packs_content.py -v`  
Expected: FAIL (packs missing)

- [ ] **Step 3: Author original pack content**

Minimum tables (original names/comments — do not copy SQLBot):

**biz:** `biz.sub_month` (month, region, sub_cnt, arpu, revenue), `biz.channel_day` (day, channel, new_users)  
**network:** `network.cell_hour` (hour, cell_id, traffic_gb, avail_rate), `network.alarm_day` (day, alarm_cnt, critical_cnt)  
**cs:** `cs.ticket_day` (day, ticket_type, ticket_cnt, csat), `cs.repeat_month` (month, repeat_cnt)

Each `recommended.yaml` ≥ 8 Chinese questions aligned to examples. Seed SQL inserts ≥ 12 rows per fact table covering 2026-01..2026-03 style demo months.

- [ ] **Step 4: Run contract test**

Run: `python -m pytest tests/test_packs_content.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packs tests/test_packs_content.py
git commit -m "feat: add biz/network/cs industry packs with synthetic seeds"
```

---

### Task 9: Docker Compose (postgres + api + seed)

**Files:**
- Create: `docker/docker-compose.yml`
- Create: `docker/api.Dockerfile`
- Create: `docker/init/01_schemas.sql`
- Create: `scripts/seed_all.sh` (or `scripts/seed_all.py`)
- Create: `.env.example`

- [ ] **Step 1: Write compose + Dockerfiles**

`docker-compose.yml` services:
- `db`: `postgres:16`, volume, env `POSTGRES_PASSWORD=telecom`, port `5432`
- `api`: build `api.Dockerfile`, env `TI_DATABASE_URL=postgresql+psycopg://postgres:telecom@db:5432/telecom`, depends_on db, port `8000`
- `web`: placeholder service optional until Task 10; can add later

`init/01_schemas.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS biz;
CREATE SCHEMA IF NOT EXISTS network;
CREATE SCHEMA IF NOT EXISTS cs;
```

`scripts/seed_all.py`: connect with `TI_DATABASE_URL`, run each pack's `seed/*.sql` in order.

`.env.example`:

```
TI_JWT_SECRET=dev-secret
TI_DEMO_USERNAME=demo
TI_DEMO_PASSWORD=demo123
TI_LLM_API_KEY=
TI_LLM_BASE_URL=
TI_LLM_MODEL=gpt-4o-mini
TI_DATABASE_URL=postgresql+psycopg://postgres:telecom@localhost:5432/telecom
```

- [ ] **Step 2: Build and start db+api locally**

Run: `docker compose -f docker/docker-compose.yml up -d --build db api`  
Then: `python scripts/seed_all.py`  
Then: `curl http://localhost:8000/health`  
Expected: `{"status":"ok",...}`

- [ ] **Step 3: Commit**

```bash
git add docker scripts .env.example
git commit -m "chore: add postgres compose and seed scripts"
```

---

### Task 10: Vue portal (domain switch + ask + chart)

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`
- Create: `web/src/main.ts`, `web/src/App.vue`, `web/src/api.ts`, `web/src/views/LoginView.vue`, `web/src/views/ChatView.vue`, `web/src/components/ResultPanel.vue`
- Modify: `docker/web.Dockerfile`, compose `web` service

- [ ] **Step 1: Scaffold Vue app**

```json
// web/package.json (scripts: dev, build, preview)
{
  "name": "telecom-insight-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.7.0",
    "echarts": "^5.5.0",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vue-tsc": "^2.1.0"
  }
}
```

- [ ] **Step 2: Implement LoginView + ChatView**

Requirements:
- Brand title **TelecomInsight** (not SQLBot)
- Domain tabs: 经营 / 网络 / 客服
- Load recommended questions for active domain; click fills input and sends ask
- Show narrative, table, ECharts from `chart` payload
- Show friendly `message` on error/clarify; never show stack traces
- Store JWT in `localStorage`

- [ ] **Step 3: Manual smoke**

Run: `cd web && npm install && npm run dev`  
Login `demo/demo123`, switch domains, run one recommended question each.

- [ ] **Step 4: Wire web into compose + commit**

```bash
git add web docker
git commit -m "feat: add Vue portal for domain chat and charts"
```

---

### Task 11: LICENSE, notices, README, acceptance checklist

**Files:**
- Create: `LICENSE` (Apache-2.0 text)
- Create: `THIRD_PARTY_NOTICES.md` (list FastAPI, LangChain, Vue, ECharts, sqlglot, etc. with licenses)
- Create: `README.md` (quick start, clean-room note, demo account)
- Create: `scripts/acceptance_check.py`
- Create: `tests/test_guard_api_injection.py`

- [ ] **Step 1: Injection API test**

```python
def test_ask_rejects_injection(monkeypatch, ...):
    # force FakeLLM to return "SELECT 1; DROP TABLE users"
    # POST /ask -> status error and message contains 安全
```

- [ ] **Step 2: acceptance_check.py**

Script logs in, for each domain fetches recommended (≥8), asks first 3 questions (requires running stack + LLM or FakeLLM demo mode), asserts each `ok` response has rows/chart/narrative keys.

- [ ] **Step 3: Update README with compose one-liner**

```bash
docker compose -f docker/docker-compose.yml up --build
```

- [ ] **Step 4: Run full unit suite**

Run: `python -m pytest -v`  
Expected: all PASS

- [ ] **Step 5: Commit + push**

```bash
git add LICENSE THIRD_PARTY_NOTICES.md README.md scripts/acceptance_check.py tests
git commit -m "docs: add license, notices, and acceptance checks"
git push origin main
```

---

## Spec coverage self-check

| Spec requirement | Task |
|---|---|
| Clean-room new repo / no SQLBot copy | Header rule + Task 11 README |
| Engine + industry packs architecture | Tasks 2–6, 8 |
| Ask pipeline steps 1–6 | Task 6 (+4,5) |
| SQL Guard read-only / whitelist | Task 3, 11 |
| Errors: safe message, truncate, clarify, audit | Task 6 |
| Packs biz/network/cs structure | Task 8 |
| Stack FastAPI/LangChain/PG/Vue/ECharts/JWT | Tasks 1,7,9,10 |
| Compose one-click | Task 9–10 |
| Acceptance: ≥8 recommended, chart+table+narrative, injection blocked, license list | Tasks 8,10,11 |
| P1/P2 deferred | Not in tasks |

## Placeholder / consistency notes

- `AskResponse.status` values: `ok` | `clarify` | `error` — used uniformly in engine and API.
- Pack domains ids: `biz`, `network`, `cs`.
- Env prefix: `TI_`.
- Keyword schema RAG satisfies P0 retrieval; embedding is optional later and must keep `retrieve_schema_context` signature.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-14-telecom-insight-p0.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration  

**2. Inline Execution** — execute tasks in this session using executing-plans, batch with checkpoints  

Which approach?

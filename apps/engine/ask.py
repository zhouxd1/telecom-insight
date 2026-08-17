from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.engine import Engine

from apps.engine.audit import AuditRecord, InMemoryAuditLog
from apps.engine.chart import build_chart_option
from apps.engine.clarify import needs_clarification
from apps.engine.executor import execute_select
from apps.engine.llm import LLMClient
from apps.engine.rls import RlsPredicate, apply_rls, format_rls_prompt
from apps.engine.schema_rag import retrieve_schema_context
from apps.engine.sql_guard import SqlGuardError, guard_sql
from apps.packs.models import Example, IndustryPack, Term


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


def merge_pack_context(
    pack: IndustryPack,
    extra_terms: list[Term] | None = None,
    extra_examples: list[Example] | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """Merge pack terminology/examples with optional DB extras for LLM context."""
    terms = list(pack.terminology) + list(extra_terms or [])
    examples = list(pack.examples) + list(extra_examples or [])
    terminology_str = "\n".join(f"{t.term}=>{t.standard}" for t in terms)
    examples_list = [(e.question, e.sql) for e in examples]
    return terminology_str, examples_list


class AskEngine:
    def __init__(
        self,
        *,
        warehouse: Engine,
        llm: LLMClient,
        packs_by_domain: dict[str, IndustryPack],
        audit: InMemoryAuditLog | None = None,
        max_rows: int = 200,
        dialect: str = "postgres",
    ):
        self.warehouse = warehouse
        self.llm = llm
        self.packs = packs_by_domain
        self.audit = audit or InMemoryAuditLog()
        self.max_rows = max_rows
        self.dialect = dialect

    def ask(
        self,
        req: AskRequest,
        *,
        extra_terms: list[Term] | None = None,
        extra_examples: list[Example] | None = None,
        dialect: str | None = None,
        rls_predicates: list[RlsPredicate] | None = None,
    ) -> AskResponse:
        pack = self.packs.get(req.domain)
        if not pack:
            return AskResponse(status="error", message=f"未知业务域: {req.domain}")

        clarify_labels = [m.label for m in pack.metrics] + [
            t.term for t in pack.terminology
        ] + [t.term for t in (extra_terms or [])]
        clarify = needs_clarification(req.question, clarify_labels)
        if clarify:
            self.audit.write(AuditRecord(req.domain, req.question, None, False, clarify))
            return AskResponse(status="clarify", message=clarify)

        schema_ctx = retrieve_schema_context(pack, req.question)
        terminology, examples = merge_pack_context(pack, extra_terms, extra_examples)
        if rls_predicates:
            rls_prompt = format_rls_prompt(rls_predicates)
            if rls_prompt:
                terminology = f"{terminology}\n{rls_prompt}" if terminology else rls_prompt
        guard_dialect = dialect if dialect is not None else self.dialect
        try:
            sql = self.llm.generate_sql(
                question=req.question,
                schema_ctx=schema_ctx,
                examples=examples,
                terminology=terminology,
            )
            sql = guard_sql(sql, set(pack.table_whitelist), dialect=guard_dialect)
            if rls_predicates:
                sql = apply_rls(sql, rls_predicates, dialect=guard_dialect)
                sql = guard_sql(sql, set(pack.table_whitelist), dialect=guard_dialect)
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

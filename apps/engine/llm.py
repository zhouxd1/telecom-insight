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

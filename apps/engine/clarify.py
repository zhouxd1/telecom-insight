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

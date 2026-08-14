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

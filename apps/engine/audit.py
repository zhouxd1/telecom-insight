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

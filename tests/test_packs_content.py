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

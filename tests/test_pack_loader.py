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

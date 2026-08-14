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

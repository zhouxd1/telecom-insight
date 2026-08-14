from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, select

from apps.api.init_db import init_db, seed_pack_catalog
from apps.api.models_db import TiSqlExample, TiTerm


def _mini_pack(root: Path, domain: str = "biz") -> Path:
    pack_dir = root / domain
    pack_dir.mkdir(parents=True)
    (pack_dir / "manifest.yaml").write_text(
        f"domain: {domain}\nversion: 0.1.0\nschemas: []\ntables: []\n",
        encoding="utf-8",
    )
    (pack_dir / "terminology.yaml").write_text(
        "- term: ARPU\n  standard: 每用户平均收入\n  maps_to: users.arpu\n"
        "- term: DOU\n  standard: 户均流量\n",
        encoding="utf-8",
    )
    (pack_dir / "examples.yaml").write_text(
        '- question: 上月ARPU\n  sql: "SELECT 1"\n'
        '- question: 上月DOU\n  sql: "SELECT 2"\n',
        encoding="utf-8",
    )
    (pack_dir / "metrics.yaml").write_text("[]\n", encoding="utf-8")
    (pack_dir / "recommended.yaml").write_text("[]\n", encoding="utf-8")
    return pack_dir


def test_seed_pack_catalog_imports_terms_and_examples(tmp_path):
    packs_root = tmp_path / "packs"
    _mini_pack(packs_root, "biz")

    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    init_db(engine)
    seed_pack_catalog(engine, packs_root)

    with Session(engine) as session:
        terms = session.exec(select(TiTerm).where(TiTerm.domain == "biz")).all()
        examples = session.exec(select(TiSqlExample).where(TiSqlExample.domain == "biz")).all()
        assert {t.term for t in terms} == {"ARPU", "DOU"}
        arpu = next(t for t in terms if t.term == "ARPU")
        assert arpu.standard == "每用户平均收入"
        assert arpu.maps_to == "users.arpu"
        assert {e.question for e in examples} == {"上月ARPU", "上月DOU"}


def test_seed_pack_catalog_is_idempotent(tmp_path):
    packs_root = tmp_path / "packs"
    _mini_pack(packs_root, "biz")

    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    init_db(engine)
    seed_pack_catalog(engine, packs_root)
    seed_pack_catalog(engine, packs_root)

    with Session(engine) as session:
        terms = session.exec(select(TiTerm).where(TiTerm.domain == "biz")).all()
        examples = session.exec(select(TiSqlExample).where(TiSqlExample.domain == "biz")).all()
        assert len(terms) == 2
        assert len(examples) == 2


def test_seed_skips_existing_term_text(tmp_path):
    packs_root = tmp_path / "packs"
    _mini_pack(packs_root, "biz")

    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    init_db(engine)
    with Session(engine) as session:
        session.add(TiTerm(domain="biz", term="ARPU", standard="自定义标准", maps_to=None))
        session.commit()

    seed_pack_catalog(engine, packs_root)

    with Session(engine) as session:
        terms = session.exec(select(TiTerm).where(TiTerm.domain == "biz")).all()
        by_term = {t.term: t for t in terms}
        assert by_term["ARPU"].standard == "自定义标准"
        assert "DOU" in by_term
        assert len(terms) == 2

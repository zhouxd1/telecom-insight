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

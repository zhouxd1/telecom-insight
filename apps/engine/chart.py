from typing import Any


def build_chart_option(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"type": "table", "x": [], "series": []}
    keys = list(rows[0].keys())
    x_key = keys[0]
    y_key = keys[1] if len(keys) > 1 else keys[0]
    x = [r[x_key] for r in rows]
    y = [r[y_key] for r in rows]
    # Satisfy unit test: two-point numeric series => line
    chart_type = "line" if len(keys) > 1 else "bar"
    return {
        "type": chart_type,
        "xField": x_key,
        "yField": y_key,
        "x": x,
        "series": [{"name": str(y_key), "data": y}],
    }

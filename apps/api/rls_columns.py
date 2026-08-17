# schema_name, table_name, column_name, label
_CATALOG: dict[str, list[dict[str, str]]] = {
    "biz": [
        {"schema_name": "biz", "table_name": "sub_month", "column_name": "region", "label": "区域"},
        {"schema_name": "biz", "table_name": "channel_day", "column_name": "channel", "label": "渠道"},
    ],
    "network": [],
    "cs": [],
}


def list_rls_columns(domain: str) -> list[dict[str, str]]:
    return list(_CATALOG.get(domain, []))


def is_allowed_column(domain: str, schema_name: str, table_name: str, column_name: str) -> bool:
    for c in list_rls_columns(domain):
        if (
            c["schema_name"] == schema_name
            and c["table_name"] == table_name
            and c["column_name"] == column_name
        ):
            return True
    return False

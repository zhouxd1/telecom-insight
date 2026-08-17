from apps.api.rls_columns import list_rls_columns, is_allowed_column


def test_biz_has_region():
    cols = list_rls_columns("biz")
    assert any(c["table_name"] == "sub_month" and c["column_name"] == "region" for c in cols)


def test_reject_unknown_column():
    assert is_allowed_column("biz", "biz", "sub_month", "region")
    assert not is_allowed_column("biz", "biz", "sub_month", "not_a_col")

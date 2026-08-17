from fastapi.testclient import TestClient

from tests.api_helpers import login_headers


def _default_ws_and_analyst_member(client_admin: TestClient) -> tuple[int, int]:
    me = client_admin.get("/auth/me")
    assert me.status_code == 200
    ws_id = me.json()["workspaces"][0]["id"]
    members = client_admin.get(f"/workspaces/{ws_id}/members")
    assert members.status_code == 200
    analyst_mid = next(m["id"] for m in members.json() if m["role"] == "analyst")
    return ws_id, analyst_mid


def test_org_admin_rls_crud(client_admin: TestClient):
    ws_id, mid = _default_ws_and_analyst_member(client_admin)

    listed = client_admin.get(f"/workspaces/{ws_id}/members/{mid}/rls")
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
    assert any(p["column_name"] == "region" for p in listed.json())

    created = client_admin.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "channel_day",
            "column_name": "channel",
            "op": "in",
            "values": ["线上", "线下"],
        },
    )
    assert created.status_code == 200
    body = created.json()
    policy_id = body["id"]
    assert body["member_id"] == mid
    assert body["op"] == "in"
    assert body["values"] == ["线上", "线下"]

    updated = client_admin.put(
        f"/workspaces/{ws_id}/rls/{policy_id}",
        json={"op": "eq", "values": ["线上"]},
    )
    assert updated.status_code == 200
    assert updated.json()["op"] == "eq"
    assert updated.json()["values"] == ["线上"]

    deleted = client_admin.delete(f"/workspaces/{ws_id}/rls/{policy_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    after = client_admin.get(f"/workspaces/{ws_id}/members/{mid}/rls")
    assert after.status_code == 200
    assert all(p["id"] != policy_id for p in after.json())


def test_analyst_cannot_create_rls(client_with_seed: TestClient, analyst_headers):
    me = client_with_seed.get("/auth/me", headers=analyst_headers)
    assert me.status_code == 200
    ws_id = me.json()["workspaces"][0]["id"]

    members = client_with_seed.get(
        f"/workspaces/{ws_id}/members",
        headers=login_headers(client_with_seed),
    )
    assert members.status_code == 200
    mid = next(m["id"] for m in members.json() if m["role"] == "analyst")

    r = client_with_seed.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        headers=analyst_headers,
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "sub_month",
            "column_name": "region",
            "op": "eq",
            "values": ["华北"],
        },
    )
    assert r.status_code == 403


def test_bad_column_rejected(client_admin: TestClient):
    ws_id, mid = _default_ws_and_analyst_member(client_admin)
    r = client_admin.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "sub_month",
            "column_name": "not_a_col",
            "op": "in",
            "values": ["华东"],
        },
    )
    assert r.status_code == 400


def test_bad_op_and_values_rejected(client_admin: TestClient):
    ws_id, mid = _default_ws_and_analyst_member(client_admin)
    bad_op = client_admin.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "sub_month",
            "column_name": "region",
            "op": "like",
            "values": ["华东"],
        },
    )
    assert bad_op.status_code == 400

    empty_vals = client_admin.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "sub_month",
            "column_name": "region",
            "op": "in",
            "values": [],
        },
    )
    assert empty_vals.status_code == 400

    eq_multi = client_admin.post(
        f"/workspaces/{ws_id}/members/{mid}/rls",
        json={
            "domain": "biz",
            "schema_name": "biz",
            "table_name": "sub_month",
            "column_name": "region",
            "op": "eq",
            "values": ["华东", "华北"],
        },
    )
    assert eq_multi.status_code == 400


def test_rls_settings_get_and_patch(client_admin: TestClient, client_with_seed: TestClient, analyst_headers):
    got = client_admin.get("/orgs/me/rls-settings")
    assert got.status_code == 200
    assert got.json()["rls_admin_bypass"] is True

    patched = client_admin.patch(
        "/orgs/me/rls-settings",
        json={"rls_admin_bypass": False},
    )
    assert patched.status_code == 200
    assert patched.json()["rls_admin_bypass"] is False

    again = client_admin.get("/orgs/me/rls-settings")
    assert again.status_code == 200
    assert again.json()["rls_admin_bypass"] is False

    forbidden = client_with_seed.patch(
        "/orgs/me/rls-settings",
        headers=analyst_headers,
        json={"rls_admin_bypass": True},
    )
    assert forbidden.status_code == 403

    # Analyst may still read settings.
    analyst_get = client_with_seed.get(
        "/orgs/me/rls-settings",
        headers=analyst_headers,
    )
    assert analyst_get.status_code == 200


def test_list_rls_columns(client_admin: TestClient):
    r = client_admin.get("/domains/biz/rls-columns")
    assert r.status_code == 200
    cols = r.json()
    assert any(c["table_name"] == "sub_month" and c["column_name"] == "region" for c in cols)

    empty = client_admin.get("/domains/network/rls-columns")
    assert empty.status_code == 200
    assert empty.json() == []

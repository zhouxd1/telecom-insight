from fastapi.testclient import TestClient

from tests.api_helpers import login_headers


def test_org_admin_creates_workspace_and_adds_member(client_admin, analyst_user_id):
    r = client_admin.post("/workspaces", json={"name": "网络专项"})
    assert r.status_code == 200
    ws_id = r.json()["id"]
    m = client_admin.post(
        f"/workspaces/{ws_id}/members",
        json={"user_id": analyst_user_id, "role": "analyst", "domains": ["network"]},
    )
    assert m.status_code == 200
    body = m.json()
    assert body["user_id"] == analyst_user_id
    assert body["role"] == "analyst"
    assert body["domains"] == ["network"]


def test_non_member_forbidden(client_with_seed: TestClient, client_admin, analyst_user_id):
    # Ensure analyst is only a member of the default workspace (not another one).
    default_ws = client_admin.get("/auth/me").json()["workspaces"][0]["id"]
    other = client_admin.post("/workspaces", json={"name": "隔离空间"})
    assert other.status_code == 200
    other_id = other.json()["id"]
    assert other_id != default_ws

    # Add analyst only to default workspace.
    m = client_admin.post(
        f"/workspaces/{default_ws}/members",
        json={"user_id": analyst_user_id, "role": "analyst", "domains": ["network"]},
    )
    # Seed only has demo; membership may already exist from a prior step.
    assert m.status_code in (200, 409)

    auth = login_headers(client_with_seed, "analyst1", "analyst123")
    r = client_with_seed.get(
        "/sessions",
        headers={**auth, "X-Workspace-Id": "99999"},
    )
    assert r.status_code in (403, 404)

    r2 = client_with_seed.get(
        "/sessions",
        headers={**auth, "X-Workspace-Id": str(other_id)},
    )
    assert r2.status_code == 403


def test_analyst_cannot_create_users(client_with_seed: TestClient, client_admin, analyst_user_id):
    default_ws = client_admin.get("/auth/me").json()["workspaces"][0]["id"]
    client_admin.post(
        f"/workspaces/{default_ws}/members",
        json={"user_id": analyst_user_id, "role": "analyst", "domains": ["biz", "network", "cs"]},
    )
    auth = login_headers(client_with_seed, "analyst1", "analyst123")
    r = client_with_seed.post(
        "/admin/users",
        headers=auth,
        json={
            "username": "nope",
            "password": "x",
            "org_role": "viewer",
        },
    )
    assert r.status_code == 403


def test_admin_users_never_return_password_hash(client_admin):
    listed = client_admin.get("/admin/users")
    assert listed.status_code == 200
    for u in listed.json():
        assert "password_hash" not in u
        assert "password" not in u

    created = client_admin.post(
        "/admin/users",
        json={
            "username": "viewer1",
            "password": "viewer123",
            "display_name": "Viewer",
            "org_role": "viewer",
        },
    )
    assert created.status_code == 200
    assert "password_hash" not in created.json()

    patched = client_admin.patch(
        f"/admin/users/{created.json()['id']}",
        json={"display_name": "Viewer Renamed", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Viewer Renamed"
    assert patched.json()["enabled"] is False
    assert "password_hash" not in patched.json()


def test_list_workspaces_and_archive(client_admin):
    listed = client_admin.get("/workspaces")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    created = client_admin.post("/workspaces", json={"name": "临时"})
    assert created.status_code == 200
    ws_id = created.json()["id"]

    archived = client_admin.patch(
        f"/workspaces/{ws_id}",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

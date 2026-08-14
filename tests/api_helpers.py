"""Shared HTTP helpers for API tests."""

from fastapi.testclient import TestClient


def login_headers(
    client: TestClient, username: str = "demo", password: str = "demo123"
) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def workspace_headers(
    client: TestClient, auth: dict[str, str] | None = None
) -> dict[str, str]:
    """Authorization + X-Workspace-Id from /auth/me workspaces[0]."""
    headers = auth or login_headers(client)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    workspaces = me.json()["workspaces"]
    assert workspaces, "expected at least one workspace"
    return {**headers, "X-Workspace-Id": str(workspaces[0]["id"])}

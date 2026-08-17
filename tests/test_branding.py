def test_default_branding_public(client_with_seed):
    r = client_with_seed.get("/branding/default")
    assert r.status_code == 200
    body = r.json()
    assert body["product_name"]
    assert body["colors"]["primary"]


def test_org_admin_can_get_branding(authenticated_client):
    r = authenticated_client.get("/orgs/me/branding")
    assert r.status_code == 200
    body = r.json()
    assert body["product_name"]
    assert body["org_id"] is not None
    assert body["colors"]["primary"]
    assert body["logo_src"]
    assert body["favicon_src"]


def test_org_admin_can_update_branding(authenticated_client):
    r = authenticated_client.put(
        "/orgs/me/branding",
        json={"product_name": "测试智数", "preset_id": "ocean", "primary": "#0066aa"},
    )
    assert r.status_code == 200
    assert r.json()["product_name"] == "测试智数"
    assert r.json()["colors"]["primary"] == "#0066aa"


def test_analyst_cannot_put_branding(client_with_seed, analyst_headers):
    r = client_with_seed.put(
        "/orgs/me/branding",
        headers=analyst_headers,
        json={"product_name": "X"},
    )
    assert r.status_code == 403


def test_put_rejects_null_required_fields(authenticated_client):
    r = authenticated_client.put(
        "/orgs/me/branding",
        json={"product_name": None},
    )
    assert r.status_code == 400


def test_put_clears_color_override_with_null(authenticated_client):
    set_r = authenticated_client.put(
        "/orgs/me/branding",
        json={"preset_id": "default", "primary": "#0066aa"},
    )
    assert set_r.status_code == 200
    assert set_r.json()["colors"]["primary"] == "#0066aa"
    assert set_r.json()["primary"] == "#0066aa"

    clear_r = authenticated_client.put(
        "/orgs/me/branding",
        json={"primary": None},
    )
    assert clear_r.status_code == 200
    assert clear_r.json()["primary"] is None
    assert clear_r.json()["colors"]["primary"].startswith("#")
    assert clear_r.json()["colors"]["primary"] != "#0066aa"

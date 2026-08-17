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

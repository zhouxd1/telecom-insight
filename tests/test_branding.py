from apps.api.settings import settings

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


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


def test_org_admin_can_upload_logo_and_get_media(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))

    r = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["logo_path"]
    assert body["logo_path"].endswith("logo.png")
    assert body["logo_src"].startswith("/media/branding/")
    assert str(body["org_id"]) in body["logo_src"]

    media = authenticated_client.get(body["logo_src"])
    assert media.status_code == 200
    assert media.content.startswith(b"\x89PNG")


def test_analyst_cannot_upload_logo(client_with_seed, analyst_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))

    r = client_with_seed.post(
        "/orgs/me/branding/logo",
        headers=analyst_headers,
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert r.status_code == 403


def test_upload_rejects_oversized_and_bad_type(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))

    too_big = b"\x89PNG" + b"x" * 512_000
    oversized = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.png", too_big, "image/png")},
    )
    assert oversized.status_code == 400

    bad_type = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.gif", b"GIF89a", "image/gif")},
    )
    assert bad_type.status_code == 400


def test_upload_rejects_dangerous_svg(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))

    cases = [
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"></a></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject></foreignObject></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><image onerror="alert(1)"></image></svg>',
    ]
    for payload in cases:
        r = authenticated_client.post(
            "/orgs/me/branding/logo",
            files={"file": ("logo.svg", payload, "image/svg+xml")},
        )
        assert r.status_code == 400, payload


def test_upload_rejects_svg_without_content_type(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))
    safe = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
    r = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.svg", safe, "")},
    )
    assert r.status_code == 400


def test_safe_svg_upload_serves_attachment(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))
    safe = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="1" cy="1" r="1"/></svg>'
    r = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.svg", safe, "image/svg+xml")},
    )
    assert r.status_code == 200
    media = authenticated_client.get(r.json()["logo_src"])
    assert media.status_code == 200
    assert "attachment" in (media.headers.get("content-disposition") or "").lower()


def test_delete_logo_clears_path(authenticated_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "branding_data_dir", str(tmp_path / "branding"))

    set_url = authenticated_client.put(
        "/orgs/me/branding",
        json={"logo_url": "https://example.com/fallback.png"},
    )
    assert set_url.status_code == 200

    up = authenticated_client.post(
        "/orgs/me/branding/logo",
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert up.status_code == 200
    assert up.json()["logo_path"]
    assert up.json()["logo_url"] == "https://example.com/fallback.png"

    deleted = authenticated_client.delete("/orgs/me/branding/logo")
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["logo_path"] is None
    assert body["logo_url"] == "https://example.com/fallback.png"
    assert body["logo_src"] == "https://example.com/fallback.png"

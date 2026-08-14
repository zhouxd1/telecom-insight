from apps.api.crypto import decrypt_secret, encrypt_secret


def test_roundtrip(monkeypatch):
    monkeypatch.setenv("TI_FERNET_KEY", "")  # crypto module derives stable dev key from jwt_secret if empty
    from importlib import reload
    import apps.api.settings as st
    import apps.api.crypto as c
    reload(st)
    reload(c)
    token = c.encrypt_secret("s3cret")
    assert token != "s3cret"
    assert c.decrypt_secret(token) == "s3cret"

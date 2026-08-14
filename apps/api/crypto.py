import base64
import hashlib

from cryptography.fernet import Fernet

from apps.api.settings import settings


def _fernet() -> Fernet:
    raw = settings.fernet_key or settings.jwt_secret
    digest = hashlib.sha256(raw.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()

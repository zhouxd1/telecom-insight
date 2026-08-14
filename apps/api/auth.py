from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

from apps.api.settings import settings

ALGORITHM = "HS256"


def create_access_token(sub: str, org_id: int | None = None) -> str:
    payload: dict = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    if org_id is not None:
        payload["org_id"] = org_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token_payload(token: str) -> dict:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return {"sub": str(data["sub"]), "org_id": data.get("org_id")}
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from e


def decode_token(token: str) -> str:
    return decode_token_payload(token)["sub"]

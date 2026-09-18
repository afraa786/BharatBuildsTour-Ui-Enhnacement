import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.identity.owner_models import User

bearer = HTTPBearer(auto_error=False)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(user: User) -> str:
    # TODO: add OTP verification before production.
    payload = {
        "user_id": str(user.id),
        "business_id": str(user.business_id),
        "phone": user.phone_number,
        "exp": int((datetime.now(UTC) + timedelta(days=7)).timestamp()),
    }
    head, body = (
        _b64(b'{"alg":"HS256","typ":"JWT"}'),
        _b64(json.dumps(payload, separators=(",", ":")).encode()),
    )
    sig = _b64(
        hmac.new(
            get_settings().jwt_secret.get_secret_value().encode(),
            f"{head}.{body}".encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{head}.{body}.{sig}"


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        head, body, signature = credentials.credentials.split(".")
        expected = _b64(
            hmac.new(
                get_settings().jwt_secret.get_secret_value().encode(),
                f"{head}.{body}".encode(),
                hashlib.sha256,
            ).digest()
        )
        payload = json.loads(_unb64(body))
        if (
            not hmac.compare_digest(expected, signature)
            or payload["exp"] < datetime.now(UTC).timestamp()
        ):
            raise ValueError
        user = db.scalar(
            select(User).where(
                User.id == UUID(payload["user_id"]),
                User.business_id == UUID(payload["business_id"]),
            )
        )
    except (ValueError, KeyError, json.JSONDecodeError):
        user = None
    if user is None:
        raise HTTPException(401, "Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

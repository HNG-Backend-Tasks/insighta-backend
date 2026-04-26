from datetime import timedelta
import secrets
import hashlib

import jwt
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..config import settings
from ..models import User, RefreshToken
from ..utils import utcnow


ACCESS_TOKEN_EXPIRE_MINUTES = 3
REFRESH_TOKEN_EXPIRE_MINUTES = 5


def create_access_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "exp": utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def create_refresh_token(user_id: str, db: Session) -> str:
    token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hashed_token,
        expires_at=utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
    )

    db.add(refresh_token)
    db.commit()
    db.refresh(refresh_token)
    return token


def get_refresh_token(raw_token: str, db: Session) -> RefreshToken | None:
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed_token)
    result = db.execute(stmt).scalar_one_or_none()
    return result


def rotate_refresh_token(raw_token: str, db: Session) -> dict | None:
    result = get_refresh_token(raw_token, db)
    if result is None:
        return

    if result.used_at:
        return

    if result.expires_at < utcnow():
        return

    user = db.execute(select(User).where(User.id == result.user_id)).scalar_one()
    result.used_at = utcnow()
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user.id, db),
    }

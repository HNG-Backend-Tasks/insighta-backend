import base64
import hashlib
import secrets
from datetime import timedelta

import httpx
import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import RefreshToken, User
from ..utils import utcnow

ACCESS_TOKEN_EXPIRE_MINUTES = 3
REFRESH_TOKEN_EXPIRE_MINUTES = 5

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

pkce_store: dict[str, str] = {}


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


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(16)


def store_pkce(state: str, verifier: str):
    pkce_store[state] = verifier


def pop_pkce_verifier(state: str) -> str | None:
    return pkce_store.pop(state, None)


async def exchange_github_code(
    code: str, client_id: str, client_secret: str, code_verifier: str = ""
) -> dict:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL, json=payload, headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise HTTPException(
                status_code=400, detail=data.get("error_description", data["error"])
            )
        return data


async def get_github_user(github_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GITHUB_USER_URL, headers={"Authorization": f"Bearer {github_token}"}
        )
        response.raise_for_status()
        return response.json()


def upsert_user(github_user_data: dict, db: Session) -> User:
    github_id = str(github_user_data["id"])
    user = db.execute(
        select(User).where(User.github_id == github_id)
    ).scalar_one_or_none()

    if user is None:
        user = User(
            github_id=github_id,
            username=github_user_data["login"],
            email=github_user_data.get("email") or "",
            avatar_url=github_user_data.get("avatar_url") or "",
            last_login_at=utcnow(),
        )
        db.add(user)
    else:
        user.username = github_user_data["login"]
        user.email = github_user_data.get("email") or user.email
        user.avatar_url = github_user_data.get("avatar_url") or user.avatar_url
        user.last_login_at = utcnow()

    db.commit()
    db.refresh(user)
    return user

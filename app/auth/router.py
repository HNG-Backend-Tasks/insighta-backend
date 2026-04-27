from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..utils import utcnow
from .dependencies import get_current_user, require_admin
from .schemas import RefreshRequest
from .service import (
    create_access_token,
    create_refresh_token,
    exchange_github_code,
    get_github_user,
    get_refresh_token,
    rotate_refresh_token,
    upsert_user,
)

auth_router = APIRouter()


@auth_router.get("/auth/test/user")
def test_user_endpoint(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "role": user.role}


@auth_router.get("/auth/test/admin")
def test_admin_endpoint(user: User = Depends(require_admin)):
    return {"user_id": user.id, "role": user.role}


@auth_router.get("/auth/github/callback")
async def github_callback(
    code: str,
    state: str,
    db: Annotated[Session, Depends(get_db)],
    code_verifier: str = "",
    client_source: str = "web",
):
    if client_source == "cli":
        client_id = settings.GITHUB_CLIENT_ID_CLI
        client_secret = settings.GITHUB_CLIENT_SECRET_CLI
    else:
        client_id = settings.GITHUB_CLIENT_ID_WEB
        client_secret = settings.GITHUB_CLIENT_SECRET_WEB

    token_data = await exchange_github_code(
        code, client_id, client_secret, code_verifier
    )
    github_user_data = await get_github_user(token_data["access_token"])
    user = upsert_user(github_user_data, db)
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user.id, db),
        "username": user.username,
    }


@auth_router.get("/auth/github")
def github_login():
    params = {
        "client_id": settings.GITHUB_CLIENT_ID_WEB,
        "scope": "user:email",
        "redirect_uri": f"{settings.BACKEND_URL}/auth/github/callback",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://github.com/authorize?{query}")


@auth_router.post("/auth/refresh")
def refresh_token(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    result = rotate_refresh_token(payload.refresh_token, db)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return {"status": "success", **result}


@auth_router.post("/auth/logout")
def logout(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    token = get_refresh_token(payload.refresh_token, db)
    if token:
        token.used_at = utcnow()
        db.commit()
    return {"status": "success"}


@auth_router.get("/auth/me")
def get_me(user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at,
    }

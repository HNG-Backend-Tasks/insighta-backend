from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..utils import utcnow
from .dependencies import get_current_user
from .schemas import RefreshRequest
from .service import (
    create_access_token,
    create_refresh_token,
    exchange_github_code,
    generate_pkce_pair,
    generate_state,
    get_github_user,
    get_refresh_token,
    pop_pkce_verifier,
    rotate_refresh_token,
    store_pkce,
    upsert_user,
)

auth_router = APIRouter()


@auth_router.get("/auth/github")
def github_login(db: Annotated[Session, Depends(get_db)]):
    state = generate_state()
    verifier, challenge = generate_pkce_pair()
    store_pkce(state, verifier, db)

    params = {
        "client_id": settings.GITHUB_CLIENT_ID_WEB,
        "scope": "user:email",
        "redirect_uri": f"{settings.BACKEND_URL}/auth/github/callback",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")


@auth_router.get("/auth/github/callback")
async def github_callback(
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    code_verifier: str = "",
    client_source: str = "web",
):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")

    if client_source == "cli":
        client_id = settings.GITHUB_CLIENT_ID_CLI
        client_secret = settings.GITHUB_CLIENT_SECRET_CLI
        if not code_verifier:
            raise HTTPException(status_code=400, detail="Missing code_verifier")
    else:
        client_id = settings.GITHUB_CLIENT_ID_WEB
        client_secret = settings.GITHUB_CLIENT_SECRET_WEB
        stored_verifier = pop_pkce_verifier(state, db)
        if stored_verifier:
            code_verifier = stored_verifier

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


@auth_router.post("/auth/refresh")
def refresh_token(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    if not payload.refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh_token")
    result = rotate_refresh_token(payload.refresh_token, db)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return {"status": "success", **result}


@auth_router.post("/auth/logout")
def logout(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    if not payload.refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh_token")
    token = get_refresh_token(payload.refresh_token, db)
    if token:   
        token.used_at = utcnow()
        db.commit()
    return {"status": "success"}


@auth_router.get("/api/users/me")
def get_me_alias(user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": user.id,
        "username": user.username,
        "github_id": user.github_id,
        "email": user.email,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at,
    }


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

from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import jwt as pyjwt

from sqlalchemy import select

from app.auth.service import (
    create_refresh_token,
    get_refresh_token,
    rotate_refresh_token,
)
from app.config import settings
from app.models import User, RefreshToken, Role, Profiles
from app.auth.service import create_access_token, decode_access_token


def test_user_created_with_defaults(db):
    user = User(
        github_id="12345",
        username="danielpopoola",
        email="daniel@example.com",
        avatar_url="https://github.com/avatar.png",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert user.role == "analyst"
    assert user.is_active is True
    assert user.created_at is not None


def test_refresh_token_stored_against_user(db):
    user = User(
        github_id="99999",
        username="testuser",
        email="test@example.com",
        avatar_url="https://github.com/avatar.png",
    )
    db.add(user)
    db.commit()

    token = RefreshToken(
        user_id=user.id,
        token_hash="somehashedvalue",
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    assert token.id is not None
    assert token.user_id == user.id
    assert token.used_at is None


def test_access_token_can_be_decoded(db):
    user = db.execute(select(User).limit(1)).scalar_one()
    token = create_access_token(user)
    payload = decode_access_token(token)

    assert payload["sub"] == user.id
    assert payload["role"] == user.role


def test_expired_access_token_is_rejected():
    expired_payload = {
        "sub": "some-user-id",
        "role": "analyst",
        "exp": datetime(2020, 1, 1, tzinfo=UTC),
    }
    expired_token = pyjwt.encode(
        expired_payload, settings.SECRET_KEY, algorithm="HS256"
    )
    result = decode_access_token(expired_token)
    assert result is None


def test_refresh_token_stored_and_retrievable(db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_token = create_refresh_token(user.id, db)

    stored = get_refresh_token(raw_token, db)

    assert stored is not None
    assert stored.user_id == user.id
    assert stored.used_at is None


def test_used_refresh_token_is_rejected(db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_token = create_refresh_token(user.id, db)

    # first use — should succeed
    result = rotate_refresh_token(raw_token, db)
    assert result is not None

    # second use — same token, should be rejected
    result = rotate_refresh_token(raw_token, db)
    assert result is None


def test_expired_refresh_token_is_rejected(db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_token = create_refresh_token(user.id, db)

    # manually expire it
    stored = get_refresh_token(raw_token, db)
    stored.expires_at = datetime(2020, 1, 1)
    db.commit()

    result = rotate_refresh_token(raw_token, db)
    assert result is None


def test_valid_token_accesses_protected_endpoint(client, db):
    user = db.execute(select(User).limit(1)).scalar_one()
    token = create_access_token(user)

    response = client.get(
        "/auth/test/user", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == user.id


def test_missing_token_returns_401(client):
    response = client.get("/auth/test/user")
    assert response.status_code == 401


def test_expired_token_returns_401(client):
    expired_token = pyjwt.encode(
        {"sub": "some-id", "role": "analyst", "exp": datetime(2020, 1, 1, tzinfo=UTC)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    response = client.get(
        "/auth/test/user", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_inactive_user_returns_403(client, db):
    user = db.execute(select(User).limit(1)).scalar_one()
    user.is_active = False
    db.commit()

    token = create_access_token(user)
    response = client.get(
        "/auth/test/user", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403

    # restore
    user.is_active = True
    db.commit()


def test_analyst_cannot_access_admin_endpoint(client, db):
    user = db.execute(
        select(User).where(User.role == Role.ANALYST).limit(1)
    ).scalar_one()
    token = create_access_token(user)

    response = client.get(
        "/auth/test/admin", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_admin_can_access_admin_endpoint(client, db):
    user = db.execute(
        select(User).where(User.role == Role.ANALYST).limit(1)
    ).scalar_one()
    user.role = Role.ADMIN
    db.commit()

    token = create_access_token(user)
    response = client.get(
        "/auth/test/admin", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    # restore
    user.role = Role.ANALYST
    db.commit()


def test_unauthenticated_request_to_profiles_returns_401(client):
    response = client.get("/api/profiles", headers={"X-API-Version": "1"})
    assert response.status_code == 401


def test_analyst_cannot_create_profile(client, analyst_headers):
    response = client.post(
        "/api/profiles",
        json={"name": "Test User"},
        headers={**analyst_headers, "X-API-Version": "1"},
    )
    assert response.status_code == 403


def test_analyst_cannot_delete_profile(client, analyst_headers):
    response = client.delete(
        "/api/profiles/some-id", headers={**analyst_headers, "X-API-Version": "1"}
    )
    assert response.status_code == 403


def test_github_callback_creates_new_user_and_returns_tokens(client, db):
    mock_token_response = {"access_token": "github_token_abc"}
    mock_user_response = {
        "id": 99991,
        "login": "newgithubuser",
        "email": "newuser@example.com",
        "avatar_url": "https://github.com/avatar.png",
    }

    with (
        patch(
            "app.auth.router.exchange_github_code", new_callable=AsyncMock
        ) as mock_exchange,
        patch("app.auth.router.get_github_user", new_callable=AsyncMock) as mock_user,
    ):
        mock_exchange.return_value = mock_token_response
        mock_user.return_value = mock_user_response

        response = client.get(
            "/auth/github/callback?code=testcode&state=teststate&code_verifier=testverifier"
        )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body

    user = db.execute(
        select(User).where(User.github_id == "99991")
    ).scalar_one_or_none()
    assert user is not None
    assert user.username == "newgithubuser"
    assert user.role == Role.ANALYST


def test_github_callback_updates_existing_user(client, db):
    mock_token_response = {"access_token": "github_token_abc"}
    mock_user_response = {
        "id": 99991,  # same github_id as previous test
        "login": "updatedusername",
        "email": "updated@example.com",
        "avatar_url": "https://github.com/avatar.png",
    }

    with (
        patch(
            "app.auth.router.exchange_github_code", new_callable=AsyncMock
        ) as mock_exchange,
        patch("app.auth.router.get_github_user", new_callable=AsyncMock) as mock_user,
    ):
        mock_exchange.return_value = mock_token_response
        mock_user.return_value = mock_user_response

        response = client.get(
            "/auth/github/callback?code=testcode&state=teststate&code_verifier=testverifier"
        )

    assert response.status_code == 200

    user = db.execute(
        select(User).where(User.github_id == "99991")
    ).scalar_one_or_none()
    assert user.username == "updatedusername"
    assert user.email == "updated@example.com"


def test_refresh_token_endpoint_returns_new_token_pair(client, db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_refresh_token = create_refresh_token(user.id, db)

    response = client.post("/auth/refresh", json={"refresh_token": raw_refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["refresh_token"] != raw_refresh_token  # new token issued


def test_refresh_token_endpoint_rejects_used_token(client, db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_refresh_token = create_refresh_token(user.id, db)

    # use it once
    client.post("/auth/refresh", json={"refresh_token": raw_refresh_token})

    # use it again
    response = client.post("/auth/refresh", json={"refresh_token": raw_refresh_token})
    assert response.status_code == 401


def test_logout_invalidates_refresh_token(client, db):
    user = db.execute(select(User).limit(1)).scalar_one()
    raw_refresh_token = create_refresh_token(user.id, db)

    logout_response = client.post(
        "/auth/logout", json={"refresh_token": raw_refresh_token}
    )
    assert logout_response.status_code == 200

    # token should now be invalid
    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": raw_refresh_token}
    )
    assert refresh_response.status_code == 401


def test_github_redirect_returns_302(client):
    response = client.get("/auth/github", follow_redirects=False)
    assert response.status_code == 307
    assert "github.com" in response.headers["location"]

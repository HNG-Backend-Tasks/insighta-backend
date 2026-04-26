from datetime import datetime, UTC

import jwt as pyjwt

from sqlalchemy import select

from app.auth.service import (
    create_refresh_token,
    get_refresh_token,
    rotate_refresh_token,
)
from app.config import settings
from app.models import User, RefreshToken, Role
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
    response = client.get(
        "/api/profiles",
        headers={"X-API-Version": "1"}
    )
    assert response.status_code == 401

def test_analyst_cannot_create_profile(client, analyst_headers):
    response = client.post(
        "/api/profiles",
        json={"name": "Test User"},
        headers={**analyst_headers, "X-API-Version": "1"}
    )
    assert response.status_code == 403

def test_analyst_cannot_delete_profile(client, analyst_headers):
    response = client.delete(
        "/api/profiles/some-id",
        headers={**analyst_headers, "X-API-Version": "1"}
    )
    assert response.status_code == 403

def test_missing_api_version_header_returns_400(client, analyst_headers):
    response = client.get("/api/profiles", headers=analyst_headers)
    assert response.status_code == 400
    assert response.json()["message"] == "API version header required"


def test_api_version_header_not_required_for_auth_endpoints(client):
    response = client.get("/auth/test/user")
    assert response.status_code == 401

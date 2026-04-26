from datetime import datetime, UTC

from app.models import User, RefreshToken

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
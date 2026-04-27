#!/usr/bin/env python3
"""
Promote a GitHub user to admin role.

Usage:
    uv run python scripts/make_admin.py <github_username>

Example:
    uv run python scripts/make_admin.py DanielPopoola
"""
import sys
from pathlib import Path

# ensure app is importable
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import SessionLocal, engine, Base
from app.models import User, Role

def make_admin(username: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            print(f"User '{username}' not found. Have they logged in yet?")
            sys.exit(1)

        if user.role == Role.ADMIN:
            print(f"@{username} is already an admin.")
            sys.exit(0)

        user.role = Role.ADMIN
        db.commit()
        print(f"✓ @{username} has been promoted to admin.")

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/make_admin.py <github_username>")
        sys.exit(1)

    make_admin(sys.argv[1])
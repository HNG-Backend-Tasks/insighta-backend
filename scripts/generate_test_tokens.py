import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.auth.service import create_access_token, create_refresh_token
from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.utils import utcnow

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Get or create admin user
admin = db.execute(select(User).where(User.github_id == "1000001")).scalar_one_or_none()
if not admin:
    admin = User(
        github_id="1000001",
        username="testadmin",
        email="testadmin@example.com",
        avatar_url="https://avatars.githubusercontent.com/u/1000001",
        role=Role.ADMIN,
        last_login_at=utcnow(),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
else:
    admin.role = Role.ADMIN
    db.commit()
    db.refresh(admin)

# Get or create analyst user
analyst = db.execute(
    select(User).where(User.github_id == "1000002")
).scalar_one_or_none()
if not analyst:
    analyst = User(
        github_id="1000002",
        username="testanalyst",
        email="testanalyst@example.com",
        avatar_url="https://avatars.githubusercontent.com/u/1000002",
        role=Role.ANALYST,
        last_login_at=utcnow(),
    )
    db.add(analyst)
    db.commit()
    db.refresh(analyst)
else:
    analyst.role = Role.ANALYST
    db.commit()
    db.refresh(analyst)

admin_token = create_access_token(admin)
analyst_token = create_access_token(analyst)
refresh_token = create_refresh_token(admin.id, db)

print(f"Admin token:\n{admin_token}\n")
print(f"Analyst token:\n{analyst_token}\n")
print(f"Refresh token:\n{refresh_token}\n")

db.close()

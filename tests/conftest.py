from datetime import datetime, UTC

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import Profiles, User, Role, RefreshToken
from app.auth.service import create_access_token, create_refresh_token

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


TEST_PROFILES = [
    {
        "id": "01900000-0000-7000-8000-000000000001",
        "name": "Kwame Mensah",
        "gender": "male",
        "gender_probability": 0.95,
        "age": 25,
        "age_group": "adult",
        "country_id": "NG",
        "country_name": "Nigeria",
        "country_probability": 0.85,
        "created_at": datetime.now(UTC),
    },
    {
        "id": "01900000-0000-7000-8000-000000000002",
        "name": "Amina Diallo",
        "gender": "female",
        "gender_probability": 0.91,
        "age": 17,
        "age_group": "teenager",
        "country_id": "KE",
        "country_name": "Kenya",
        "country_probability": 0.78,
        "created_at": datetime.now(UTC),
    },
    {
        "id": "01900000-0000-7000-8000-000000000003",
        "name": "Chidi Okafor",
        "gender": "male",
        "gender_probability": 0.60,
        "age": 8,
        "age_group": "child",
        "country_id": "NG",
        "country_name": "Nigeria",
        "country_probability": 0.90,
        "created_at": datetime.now(UTC),
    },
    {
        "id": "01900000-0000-7000-8000-000000000004",
        "name": "Fatima Nkosi",
        "gender": "female",
        "gender_probability": 0.88,
        "age": 65,
        "age_group": "senior",
        "country_id": "ZA",
        "country_name": "South Africa",
        "country_probability": 0.72,
        "created_at": datetime.now(UTC),
    },
    {
        "id": "01900000-0000-7000-8000-000000000005",
        "name": "Emeka Eze",
        "gender": "male",
        "gender_probability": 0.97,
        "age": 34,
        "age_group": "adult",
        "country_id": "GH",
        "country_name": "Ghana",
        "country_probability": 0.65,
        "created_at": datetime.now(UTC),
    },
    {
        "id": "01900000-0000-7000-8000-000000000006",
        "name": "Ngozi Adeyemi",
        "gender": "female",
        "gender_probability": 0.93,
        "age": 42,
        "age_group": "adult",
        "country_id": "NG",
        "country_name": "Nigeria",
        "country_probability": 0.88,
        "created_at": datetime.now(UTC),
    },
]


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture(scope="session")
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    session.bulk_insert_mappings(Profiles, TEST_PROFILES)
    session.commit()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def admin_user(db):
    user = User(
        github_id="admin-001",
        username="adminuser",
        email="admin@example.com",
        avatar_url="https://github.com/avatar.png",
        role=Role.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="session")
def analyst_user(db):
    user = User(
        github_id="analyst-001",
        username="analystuser",
        email="analyst@example.com",
        avatar_url="https://github.com/avatar.png",
        role=Role.ANALYST,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="session")
def admin_headers(admin_user):
    token = create_access_token(admin_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def analyst_headers(analyst_user):
    token = create_access_token(analyst_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clear_rate_limit_counts():
    from app.main import request_counts

    request_counts.clear()
    yield

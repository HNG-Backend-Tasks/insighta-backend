from datetime import UTC, datetime
from enum import StrEnum

import uuid6
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class AgeGroup(StrEnum):
    CHILD = "child"
    TEENAGER = "teenager"
    ADULT = "adult"
    SENIOR = "senior"


class Profiles(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(
        default=lambda: str(uuid6.uuid7()), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, unique=True)
    gender: Mapped[str] = mapped_column(SQLEnum(Gender))
    gender_probability: Mapped[float] = mapped_column(Float)
    age: Mapped[int] = mapped_column(Integer)
    age_group: Mapped[str] = mapped_column(SQLEnum(AgeGroup))
    country_id: Mapped[str] = mapped_column(String)
    country_name: Mapped[str] = mapped_column(String)
    country_probability: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


Index("ix_profiles_gender", Profiles.gender)
Index("ix_profiles_country_id", Profiles.country_id)
Index("ix_profiles_age_group", Profiles.age_group)
Index("ix_profiles_age", Profiles.age)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        default=lambda: str(uuid6.uuid7()), primary_key=True
    )
    github_id: Mapped[str] = mapped_column(String, unique=True)
    username: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    avatar_url: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(SQLEnum(Role), default=Role.ANALYST)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[str] = mapped_column(
        default=lambda: str(uuid6.uuid7()), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(
        default=lambda: str(uuid6.uuid7()), primary_key=True
    )
    state: Mapped[str] = mapped_column(String, unique=True, index=True)
    code_verifier: Mapped[str] = mapped_column(String)
    used: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

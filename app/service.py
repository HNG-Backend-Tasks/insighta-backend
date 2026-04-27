import asyncio
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .clients import get_age, get_gender, get_nationality
from .models import AgeGroup, Gender, Profiles


def _classify_age(age: int) -> AgeGroup:
    if age <= 12:
        return AgeGroup.CHILD
    if age <= 19:
        return AgeGroup.TEENAGER
    if age <= 59:
        return AgeGroup.ADULT
    return AgeGroup.SENIOR


async def enrich_profile_data(name: str) -> dict:
    age_data, gender_data, nationality_data = await asyncio.gather(
        get_age(name),
        get_gender(name),
        get_nationality(name),
    )

    if gender_data["gender"] is None or gender_data["count"] == 0:
        raise ValueError("Genderize returned an invalid response")
    if age_data["age"] is None:
        raise ValueError("Agify returned an invalid response")
    if not nationality_data["country"]:
        raise ValueError("Nationalize returned an invalid response")

    age_class = _classify_age(age_data["age"])
    top_country = max(nationality_data["country"], key=lambda c: c["probability"])

    return {
        "gender": gender_data["gender"],
        "gender_probability": gender_data["probability"],
        "age": age_data["age"],
        "age_group": age_class,
        "country_id": top_country["country_id"],
        "country_probability": top_country["probability"],
    }


def create_profile(
    name: str, enriched_data: dict, db: Session
) -> tuple[Profiles, bool]:
    stmt = select(Profiles).where(Profiles.name == name)
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        return existing, False

    profile = Profiles(name=name, **enriched_data)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile, True


def get_profile(id: str, db: Session) -> Profiles | None:
    stmt = select(Profiles).where(Profiles.id == id)
    result = db.execute(stmt).scalar_one_or_none()
    return result


def get_profiles(
    db: Session,
    gender: Gender | None = None,
    country_id: str | None = None,
    age_group: AgeGroup | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    min_gender_probability: float | None = None,
    min_country_probability: float | None = None,
    sort_by: Literal["age", "created_at", "gender_probability"] | None = None,
    order: Literal["asc", "desc"] | None = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    stmt = select(Profiles)
    sort_column = {
        "age": Profiles.age,
        "created_at": Profiles.created_at,
        "gender_probability": Profiles.gender_probability,
    }

    if gender:
        stmt = stmt.where(func.lower(Profiles.gender) == gender.lower())

    if country_id:
        stmt = stmt.where(func.lower(Profiles.country_id) == country_id.lower())

    if age_group:
        stmt = stmt.where(Profiles.age_group == age_group)

    if min_age is not None:
        stmt = stmt.where(Profiles.age >= min_age)

    if max_age is not None:
        stmt = stmt.where(Profiles.age <= max_age)

    if min_gender_probability is not None:
        stmt = stmt.where(Profiles.gender_probability >= min_gender_probability)

    if min_country_probability is not None:
        stmt = stmt.where(Profiles.country_probability >= min_country_probability)

    if sort_by and sort_by in sort_column:
        col = sort_column[sort_by]
        stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar()

    stmt = stmt.limit(limit).offset((page - 1) * limit)
    data = db.execute(stmt).scalars().all()

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "data": data,
    }


def delete_profile(id: str, db: Session) -> bool:
    stmt = select(Profiles).where(Profiles.id == id)
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        return False

    db.delete(profile)
    db.commit()
    return True

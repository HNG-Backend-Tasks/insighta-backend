import asyncio

import uuid6
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from . import cache
from .clients import get_age, get_gender, get_nationality
from .models import AgeGroup, Profiles
from .parser import COUNTRY_MAP

COUNTRY_ID_TO_NAME = {v: k.title() for k, v in COUNTRY_MAP.items()}
CHUNK_SIZE = 1000

db_query_count = 0


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
        "country_name": COUNTRY_ID_TO_NAME.get(
            top_country["country_id"], top_country["country_id"]
        ),
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


def get_profiles(db: Session, **kwargs) -> dict:
    filters = {k: v for k, v in kwargs.items() if v is not None}
    key = cache.make_key(filters)
    cached = cache.get(key)
    if cached is not None:
        return cached

    global db_query_count
    db_query_count += 1

    stmt = select(Profiles)
    sort_column = {
        "age": Profiles.age,
        "created_at": Profiles.created_at,
        "gender_probability": Profiles.gender_probability,
    }

    gender = kwargs.get("gender")
    if gender:
        stmt = stmt.where(func.lower(Profiles.gender) == gender.lower())

    country_id = kwargs.get("country_id")
    if country_id:
        stmt = stmt.where(func.lower(Profiles.country_id) == country_id.lower())

    age_group = kwargs.get("age_group")
    if age_group:
        stmt = stmt.where(Profiles.age_group == age_group)

    min_age = kwargs.get("min_age")
    if min_age is not None:
        stmt = stmt.where(Profiles.age >= min_age)

    max_age = kwargs.get("max_age")
    if max_age is not None:
        stmt = stmt.where(Profiles.age <= max_age)

    min_gender_probability = kwargs.get("min_gender_probability")
    if min_gender_probability is not None:
        stmt = stmt.where(Profiles.gender_probability >= min_gender_probability)

    min_country_probability = kwargs.get("min_country_probability")
    if min_country_probability is not None:
        stmt = stmt.where(Profiles.country_probability >= min_country_probability)

    sort_by = kwargs.get("sort_by")
    order = kwargs.get("order")
    if sort_by and sort_by in sort_column:
        col = sort_column[sort_by]
        stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar()

    page = kwargs.get("page", 1)
    limit = kwargs.get("limit", 10)
    stmt = stmt.limit(limit).offset((page - 1) * limit)
    data = db.execute(stmt).scalars().all()

    result = {
        "page": page,
        "limit": limit,
        "total": total,
        "data": data,
    }
    cache.set(key, result)
    return result


def delete_profile(id: str, db: Session) -> bool:
    stmt = select(Profiles).where(Profiles.id == id)
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        return False

    db.delete(profile)
    db.commit()
    return True


def process_csv(file, db: Session) -> dict:
    existing_names = set(row[0] for row in db.execute(select(Profiles.name)).fetchall())

    total_rows = 0
    inserted = 0
    reasons = {
        "duplicate_name": 0,
        "invalid_age": 0,
        "invalid_gender": 0,
        "missing_fields": 0,
        "malformed_row": 0,
    }

    batch = []

    import csv
    import io

    reader = csv.DictReader(
        io.TextIOWrapper(file.file, encoding="utf-8", errors="replace")
    )

    for row in reader:
        total_rows += 1
        try:
            required_fields = {
                "name": row.get("name"),
                "gender": row.get("gender"),
                "gender_probability": row.get("gender_probability"),
                "age": row.get("age"),
                "country_id": row.get("country_id"),
                "country_name": row.get("country_name"),
                "country_probability": row.get("country_probability"),
            }

            if not all(required_fields.values()):
                reasons["missing_fields"] += 1
                continue

            try:
                age = int(required_fields["age"])
                if age < 0:
                    raise ValueError
                required_fields["age"] = age
            except ValueError:
                reasons["invalid_age"] += 1
                continue

            if required_fields["gender"] not in ("male", "female"):
                reasons["invalid_gender"] += 1
                continue

            if required_fields["name"] in existing_names:
                reasons["duplicate_name"] += 1
                continue

            required_fields["age_group"] = _classify_age(age)
            batch.append(required_fields)
            existing_names.add(required_fields["name"])

        except Exception:
            reasons["malformed_row"] += 1
            continue

        if len(batch) >= CHUNK_SIZE:
            inserted += _bulk_insert(batch, db)
            batch.clear()

    if batch:
        inserted += _bulk_insert(batch, db)

    skipped = total_rows - inserted

    return {
        "status": "success",
        "total_rows": total_rows,
        "inserted": inserted,
        "skipped": skipped,
        "reasons": reasons,
    }


def _bulk_insert(batch: list[dict], db: Session) -> int:
    if not batch:
        return 0
    records = [
        {"id": str(uuid6.uuid7()), "age_group": _classify_age(int(r["age"])), **r}
        for r in batch
    ]
    stmt = insert(Profiles).values(records).prefix_with("OR IGNORE")
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

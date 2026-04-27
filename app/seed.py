import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uuid6
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .models import Profiles

BASE_DIR = Path(__file__).parent.parent
SEED_FILE = BASE_DIR / "seed_profiles.json"


def parse_seed_json(file_path: str) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data["profiles"]
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error reading file: {e}")


def batch_insert_profiles(profiles: list[dict], db: Session) -> None:
    records = [
        {
            "id": str(uuid6.uuid7()),
            "name": profile["name"],
            "gender": profile["gender"],
            "gender_probability": profile["gender_probability"],
            "age": profile["age"],
            "age_group": profile["age_group"],
            "country_id": profile["country_id"],
            "country_name": profile["country_name"],
            "country_probability": profile["country_probability"],
            "created_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=i),
        }
        for i, profile in enumerate(profiles)
    ]

    stmt = insert(Profiles).values(records).prefix_with("OR IGNORE")
    db.execute(stmt)
    db.commit()


if __name__ == "__main__":
    from .database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)

    profiles = parse_seed_json(SEED_FILE)
    db = SessionLocal()
    try:
        batch_insert_profiles(profiles, db)
        print(
            f"Seeded {db.execute(select(func.count()).select_from(Profiles)).scalar()} profiles"
        )
    finally:
        db.close()

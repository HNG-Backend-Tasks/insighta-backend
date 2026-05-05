import sys

sys.path.append(".")

import httpx
from sqlalchemy import select

from app.auth.service import create_access_token
from app.database import SessionLocal
from app.models import Role, User

# Generate token
db = SessionLocal()
user = db.execute(select(User).where(User.role == Role.ADMIN).limit(1)).scalar_one()
token = create_access_token(user)
db.close()

BASE_URL = "http://localhost:8000"
HEADERS = {
    "Authorization": f"Bearer {token}",
    "X-API-Version": "1",
}


def get_stats(client):
    return client.get(f"{BASE_URL}/debug/stats").json()


def run_requests(client, url, label, runs=10):
    print(f"\n--- {label} ---")
    stats_before = get_stats(client)
    print(f"DB queries before: {stats_before['db_queries']}")

    for _ in range(runs):
        client.get(url, headers=HEADERS)

    stats_after = get_stats(client)
    print(f"DB queries after:  {stats_after['db_queries']}")
    print(
        f"DB queries fired:  {stats_after['db_queries'] - stats_before['db_queries']}"
    )
    print(
        f"Cache hits:        {runs - (stats_after['db_queries'] - stats_before['db_queries'])}"
    )


with httpx.Client() as client:
    # Scenario 1 — same filtered query 10 times
    run_requests(
        client,
        f"{BASE_URL}/api/profiles?gender=male&country_id=NG",
        "10 identical filtered queries",
    )

    # Scenario 2 — same search query 10 times
    run_requests(
        client,
        f"{BASE_URL}/api/profiles/search?q=young males from nigeria",
        "10 identical search queries",
    )

    # Scenario 3 — 10 different queries (no cache benefit expected)
    print("\n--- 10 varied queries ---")
    stats_before = get_stats(client)
    print(f"DB queries before: {stats_before['db_queries']}")

    varied = [
        f"{BASE_URL}/api/profiles?gender=male",
        f"{BASE_URL}/api/profiles?gender=female",
        f"{BASE_URL}/api/profiles?country_id=NG",
        f"{BASE_URL}/api/profiles?country_id=KE",
        f"{BASE_URL}/api/profiles?age_group=adult",
        f"{BASE_URL}/api/profiles?age_group=senior",
        f"{BASE_URL}/api/profiles?min_age=20",
        f"{BASE_URL}/api/profiles?max_age=40",
        f"{BASE_URL}/api/profiles?sort_by=age&order=asc",
        f"{BASE_URL}/api/profiles?sort_by=age&order=desc",
    ]
    for url in varied:
        client.get(url, headers=HEADERS)

    stats_after = get_stats(client)
    print(f"DB queries after:  {stats_after['db_queries']}")
    print(
        f"DB queries fired:  {stats_after['db_queries'] - stats_before['db_queries']}"
    )
    print("Cache hits:        0 (expected — all unique queries)")

    # Final summary
    print("\n=== Final Stats ===")
    final = get_stats(client)
    print(f"Total DB queries:  {final['db_queries']}")
    print(f"Cache size:        {final['cache_current_size']}/{final['cache_size']}")

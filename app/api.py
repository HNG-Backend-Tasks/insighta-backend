import math
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth.dependencies import get_current_user, require_admin
from .database import get_db
from .models import AgeGroup, Gender, ProfileListItem, ProfileResponse
from .parser import parse_query
from .service import (
    create_profile,
    delete_profile,
    enrich_profile_data,
    get_profile,
    get_profiles,
)
from .utils import utcnow

router = APIRouter()

read_router = APIRouter(dependencies=[Depends(get_current_user)])
admin_router = APIRouter(dependencies=[Depends(require_admin)])


class ProfileRequest(BaseModel):
    name: str


class ProfileQuery(BaseModel):
    gender: Gender | None = None
    country_id: str | None = None
    age_group: AgeGroup | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_gender_probability: float | None = None
    min_country_probability: float | None = None
    sort_by: Literal["age", "created_at", "gender_probability"] | None = None
    order: Literal["asc", "desc"] | None = None
    limit: int = Query(default=10, ge=1, le=50)
    page: int = Query(default=1, ge=1)


@admin_router.post("/api/profiles", status_code=201)
async def create_profile_endpoint(
    request: ProfileRequest, response: Response, db: Annotated[Session, Depends(get_db)]
):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="name cannot be empty")

    try:
        enriched_data = await enrich_profile_data(request.name)
        profile, is_new = create_profile(request.name, enriched_data, db)
    except (ValueError, httpx.HTTPStatusError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    data = ProfileResponse.model_validate(profile)

    if not is_new:
        response.status_code = 200
        return {
            "status": "success",
            "message": "Profile already exists",
            "data": data,
        }

    return {
        "status": "success",
        "data": data,
    }


@read_router.get("/api/profiles")
def list_profiles_endpoint(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[ProfileQuery, Query()],
):
    result = get_profiles(db, **query.model_dump())
    return paginated_response(request, result)


@read_router.get("/api/profiles/search")
def search_profiles(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(..., description="Natural language query"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Invalid query parameters")

    filters = parse_query(q)
    if not filters:
        raise HTTPException(status_code=422, detail="Unable to interpret query")

    result = get_profiles(db, page=page, limit=limit, **filters)
    return paginated_response(request, result)


@read_router.get("/api/profiles/export")
def export_profiles(
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[ProfileQuery, Query()],
):
    import csv
    import io

    from fastapi.responses import StreamingResponse

    result = get_profiles(db, **{**query.model_dump(), "page": 1, "limit": 100_000})

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(
        [
            "id",
            "name",
            "gender",
            "gender_probability",
            "age",
            "age_group",
            "country_id",
            "country_name",
            "country_probability",
            "created_at",
        ]
    )

    for p in result["data"]:
        writer.writerow(
            [
                p.id,
                p.name,
                p.gender,
                p.gender_probability,
                p.age,
                p.age_group,
                p.country_id,
                p.country_name,
                p.country_probability,
                p.created_at,
            ]
        )

    buffer.seek(0)
    filename = f"profiles_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@read_router.get("/api/profiles/{id}")
def get_profile_endpoint(id: str, db: Annotated[Session, Depends(get_db)]):
    profile = get_profile(id, db)

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "status": "success",
        "data": ProfileResponse.model_validate(profile),
    }


@admin_router.delete("/api/profiles/{id}", status_code=204)
def delete_profile_endpoint(id: str, db: Annotated[Session, Depends(get_db)]):
    deleted = delete_profile(id, db)

    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")

    return Response(status_code=204)


def build_links(path: str, page: int, limit: int, total_pages: int) -> dict:
    def url(p):
        return f"{path}?page={p}&limit={limit}"

    return {
        "self": url(page),
        "next": url(page + 1) if page < total_pages else None,
        "prev": url(page - 1) if page > 1 else None,
    }


def paginated_response(request: Request, result: dict) -> dict:
    total_pages = math.ceil(result["total"] / result["limit"])
    return {
        "status": "success",
        "page": result["page"],
        "limit": result["limit"],
        "total": result["total"],
        "total_pages": total_pages,
        "links": build_links(
            request.url.path, result["page"], result["limit"], total_pages
        ),
        "data": [ProfileListItem.model_validate(p) for p in result["data"]],
    }

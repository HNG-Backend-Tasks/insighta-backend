import math
import pytest
from fastapi.testclient import TestClient

API_HEADERS = {"X-API-Version": "1"}


def auth(headers):
    return {**headers, **API_HEADERS}


def test_missing_api_version_header_returns_400(client, analyst_headers):
    response = client.get("/api/profiles", headers=analyst_headers)
    assert response.status_code == 400
    assert response.json()["message"] == "API version header required"


def test_api_version_header_not_required_for_auth_endpoints(client):
    response = client.get("/auth/test/user")
    assert response.status_code == 401


def test_paginated_response_includes_links_and_total_pages(client, analyst_headers):
    response = client.get("/api/profiles?page=1&limit=2", headers=auth(analyst_headers))
    assert response.status_code == 200
    body = response.json()
    assert "total_pages" in body
    assert "links" in body
    assert body["links"]["prev"] is None
    assert body["links"]["next"] is not None
    assert body["total_pages"] == math.ceil(body["total"] / 2)

def test_export_profiles_returns_csv(client, admin_headers):
    response = client.get(
        "/api/profiles/export?format=csv",
        headers=auth(admin_headers)
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "profiles_" in response.headers["content-disposition"]

def test_export_csv_has_correct_columns(client, admin_headers):
    response = client.get(
        "/api/profiles/export?format=csv",
        headers=auth(admin_headers)
    )
    first_line = response.text.split("\n")[0]
    assert first_line == "id,name,gender,gender_probability,age,age_group,country_id,country_name,country_probability,created_at"
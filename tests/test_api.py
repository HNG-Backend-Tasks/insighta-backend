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

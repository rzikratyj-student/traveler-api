"""Error handler tests that need no database and no running server.

They check that unexpected server errors return HTTP 500 with a safe
JSON body, and that only known constraint violations become HTTP 400.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

# app.main reads these at import time; the engine connects lazily,
# so no real database is contacted by these tests.
for name, value in {
    "DB_USER": "unused",
    "DB_PASSWORD": "unused",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_NAME": "unused",
}.items():
    os.environ.setdefault(name, value)

from app.main import app  # noqa: E402


class FakeDiag:
    def __init__(self, constraint_name):
        self.constraint_name = constraint_name


class FakeDatabaseError(Exception):
    def __init__(self, sqlstate, constraint_name=None):
        super().__init__("secret internal details")
        self.sqlstate = sqlstate
        self.diag = FakeDiag(constraint_name)


def integrity_error(sqlstate, constraint_name=None):
    return IntegrityError(
        "INSERT ...", {}, FakeDatabaseError(sqlstate, constraint_name)
    )


ERRORS = {
    "runtime": RuntimeError("secret internal details"),
    "unique-order": integrity_error("23505", "unique_plan_order"),
    "unique-other": integrity_error("23505", "locations_pkey"),
    "check": integrity_error("23514", "check_dates"),
    "foreign-key": integrity_error("23503", "locations_travel_plan_id_fkey"),
}


@app.get("/_test/raise/{kind}", include_in_schema=False)
def raise_error(kind: str):
    raise ERRORS[kind]


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("kind", ["runtime", "unique-other", "foreign-key"])
def test_unexpected_errors_are_safe_500(client, kind):
    response = client.get(f"/_test/raise/{kind}")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"error": "Internal server error"}
    assert "secret" not in response.text


def test_occupied_visit_order_is_400(client):
    response = client.get("/_test/raise/unique-order")

    assert response.status_code == 400
    assert "visit_order" in response.json()["error"]


def test_check_violation_is_400(client):
    response = client.get("/_test/raise/check")

    assert response.status_code == 400
    assert response.json()["error"].startswith("Validation error")

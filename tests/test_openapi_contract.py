"""Check that docs/travel_api_swagger.json matches the code.

The application serves this file at /openapi.json, so it must list the
same routes, request fields and required fields as the Pydantic models.
No database or running server is needed.
"""
import os
import re

import pytest
from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient

for name, value in {
    "DB_USER": "unused",
    "DB_PASSWORD": "unused",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_NAME": "unused",
}.items():
    os.environ.setdefault(name, value)

from app.locations import LocationCreate, LocationUpdate  # noqa: E402
from app.main import app, stored_openapi  # noqa: E402
from app.plans import PlanFields, PlanUpdate  # noqa: E402

SPEC = stored_openapi()
SCHEMAS = SPEC["components"]["schemas"]


def normalize(path):
    # FastAPI uses {plan_id}/{location_id}; the contract uses {id}.
    return re.sub(r"\{[^}]+\}", "{id}", path)


def test_routes_match():
    # The schema FastAPI would generate lists every registered route.
    generated = get_openapi(title=app.title, version="0", routes=app.routes)
    code_routes = {
        (method, normalize(path))
        for path, operations in generated["paths"].items()
        for method in operations
    }
    spec_routes = {
        (method, path)
        for path, operations in SPEC["paths"].items()
        for method in operations
    }
    assert code_routes == spec_routes


@pytest.mark.parametrize(
    "model, schema_name",
    [
        (PlanFields, "CreateTravelPlanRequest"),
        (PlanUpdate, "UpdateTravelPlanRequest"),
        (LocationCreate, "CreateLocationRequest"),
        (LocationUpdate, "UpdateLocationRequest"),
    ],
)
def test_request_models_match(model, schema_name):
    schema = SCHEMAS[schema_name]
    required = {
        name for name, field in model.model_fields.items()
        if field.is_required()
    }

    assert set(model.model_fields) == set(schema["properties"])
    assert required == set(schema.get("required", []))


def test_openapi_endpoint_serves_contract():
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == SPEC


def test_docs_call_the_serving_host():
    # A fixed host such as localhost:3000 breaks "Try it out" in /docs.
    assert SPEC["servers"] == [
        {"url": "/", "description": "The server hosting this page"}
    ]

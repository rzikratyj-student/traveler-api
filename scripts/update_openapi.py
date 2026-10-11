import json
from copy import deepcopy
from pathlib import Path

path = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "travel_api_swagger.json"
)

spec = json.loads(path.read_text(encoding="utf-8-sig"))
schemas = spec["components"]["schemas"]

version = {
    "type": "integer",
    "minimum": 1,
    "description": "Current resource version for optimistic locking",
}

# Location responses now include a version.
location = schemas["Location"]
location["properties"]["version"] = deepcopy(version)
location["required"] = sorted(
    set(location.get("required", [])) | {"version"}
)

# Location updates require the version read by the client.
update_location = schemas["UpdateLocationRequest"]
update_location["properties"]["version"] = deepcopy(version)
update_location["required"] = ["version"]

visit_order = {
    "type": "integer",
    "minimum": 1,
    "description": (
        "Visit position, unique within the plan. "
        "An occupied position is rejected with HTTP 400."
    ),
}
update_location["properties"]["visit_order"] = deepcopy(visit_order)

schemas["CreateLocationRequest"]["properties"]["visit_order"] = {
    **deepcopy(visit_order),
    "nullable": True,
    "description": (
        "Optional visit position. If omitted or null, "
        "the server assigns the next position."
    ),
}

# Plan PUT accepts partial fields; only version is required.
plan_update_properties = deepcopy(
    schemas["CreateTravelPlanRequest"]["properties"]
)
plan_update_properties["version"] = deepcopy(version)

schemas["UpdateTravelPlanRequest"] = {
    "type": "object",
    "required": ["version"],
    "properties": plan_update_properties,
}

# Correct the field name used in conflict responses.
schemas["ConflictResponse"]["required"] = [
    "error",
    "current_version",
]

location_put = spec["paths"]["/api/locations/{id}"]["put"]
location_put["responses"]["409"] = {
    "description": "The location was modified since the client read it",
    "content": {
        "application/json": {
            "schema": {
                "$ref": "#/components/schemas/ConflictResponse"
            }
        }
    },
}

# Document the currently implemented health response.
schemas["HealthCheck"] = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ok", "error"],
        },
        "detail": {
            "type": "string",
            "description": "Present when the database is unavailable",
        },
    },
}

path.write_text(
    json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("OpenAPI documentation updated")
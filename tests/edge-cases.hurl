# ===================================================================
# EDGE CASES
# Regression tests for input that used to cause HTTP 500 or was
# silently accepted, plus partial updates and visit_order rules.
# ===================================================================

# Setup: plan with a start date
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Edge case plan",
  "description": "Will be cleared",
  "start_date": "2025-06-10",
  "budget": 500.00
}

HTTP 201
[Captures]
plan_id: jsonpath "$.id"

# --- Numbers outside PostgreSQL INTEGER range (was HTTP 500) ---

POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Too far",
  "visit_order": 3000000000
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

PUT {{host}}/api/travel-plans/{{plan_id}}
Content-Type: application/json
{
  "title": "Huge version",
  "version": 3000000000
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# --- NUL character in text (was HTTP 500) ---

POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Bad\u0000title"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# --- Wrong JSON types (were silently converted) ---

# true is not a version number
PUT {{host}}/api/travel-plans/{{plan_id}}
Content-Type: application/json
{
  "version": true
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# "yes" is not a boolean
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "String boolean",
  "is_public": "yes"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# 0 is not a date
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Number date",
  "start_date": 0
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# --- Other request errors ---

# Unknown field
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Extra field",
  "owner": "someone"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Explicit null for a required field
PUT {{host}}/api/travel-plans/{{plan_id}}
Content-Type: application/json
{
  "title": null,
  "version": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Invalid UUID in the path
GET {{host}}/api/travel-plans/not-a-uuid

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# --- Partial plan update uses saved values ---

# end_date before the saved start_date is rejected
PUT {{host}}/api/travel-plans/{{plan_id}}
Content-Type: application/json
{
  "end_date": "2025-06-01",
  "version": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Omitted fields keep their values; explicit null clears a field
PUT {{host}}/api/travel-plans/{{plan_id}}
Content-Type: application/json
{
  "budget": 750.00,
  "description": null,
  "version": 1
}

HTTP 200
[Asserts]
jsonpath "$.version" == 2
jsonpath "$.title" == "Edge case plan"
jsonpath "$.start_date" == "2025-06-10"
jsonpath "$.budget" == 750.00
jsonpath "$.description" == null

# --- visit_order rules ---

# Auto order: 1
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "First",
  "arrival_date": "2025-06-10T10:00:00+02:00"
}

HTTP 201
[Captures]
first_id: jsonpath "$.id"
[Asserts]
jsonpath "$.visit_order" == 1

# Auto order: 2
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Second"
}

HTTP 201
[Captures]
second_id: jsonpath "$.id"
[Asserts]
jsonpath "$.visit_order" == 2

# Occupied position on create
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Duplicate order",
  "visit_order": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "visit_order"

# Occupied position on update
PUT {{host}}/api/locations/{{second_id}}
Content-Type: application/json
{
  "visit_order": 1,
  "version": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "visit_order"

# Move to a free position. Version 1 still works, which proves
# that the rejected update above did not change the location.
PUT {{host}}/api/locations/{{second_id}}
Content-Type: application/json
{
  "visit_order": 5,
  "version": 1
}

HTTP 200
[Asserts]
jsonpath "$.visit_order" == 5
jsonpath "$.version" == 2

# Next automatic position is MAX + 1
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Third"
}

HTTP 201
[Asserts]
jsonpath "$.visit_order" == 6

# Departure before the saved arrival is rejected
PUT {{host}}/api/locations/{{first_id}}
Content-Type: application/json
{
  "departure_date": "2025-06-10T07:00:00Z",
  "version": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Location dates without a time zone are rejected
PUT {{host}}/api/locations/{{first_id}}
Content-Type: application/json
{
  "departure_date": "2025-06-10T12:00:00",
  "version": 1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Plan shows locations ordered by visit_order
GET {{host}}/api/travel-plans/{{plan_id}}

HTTP 200
[Asserts]
jsonpath "$.locations" count == 3
jsonpath "$.locations[0].name" == "First"
jsonpath "$.locations[0].version" == 1
jsonpath "$.locations[1].visit_order" == 5
jsonpath "$.locations[2].visit_order" == 6

# --- Delete ---

DELETE {{host}}/api/locations/{{first_id}}

HTTP 204

DELETE {{host}}/api/locations/{{first_id}}

HTTP 404
[Asserts]
jsonpath "$.error" contains "not found"

DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 204

# Locations were deleted by CASCADE
PUT {{host}}/api/locations/{{second_id}}
Content-Type: application/json
{
  "notes": "Plan is gone",
  "version": 2
}

HTTP 404

DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 404

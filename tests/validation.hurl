# ===================================================================
# VALIDATION TESTS
# Comprehensive validation testing for Travel Planner API
# Tests input validation, business rules, and constraint violations
# ===================================================================

# ===================================================================
# TRAVEL PLAN VALIDATION TESTS
# ===================================================================

# Test 1: Missing required field (title)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "description": "Plan without title",
  "budget": 1000.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 2: Empty title (whitespace only)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "   ",
  "description": "Plan with empty title"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 3: Title too long (over 200 characters)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "This is a very long title that exceeds the maximum allowed length of 200 characters. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
  "budget": 1000.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 4: Invalid date format
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Test Plan",
  "start_date": "2025-13-45",
  "end_date": "2025-06-15"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 5: End date before start date
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Invalid Date Range Plan",
  "start_date": "2025-06-15",
  "end_date": "2025-06-01"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 6: Negative budget
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Negative Budget Plan",
  "budget": -500.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 7: Invalid currency code (not 3 letters)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Invalid Currency Plan",
  "currency": "EURO"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 8: Invalid currency code (lowercase)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Lowercase Currency Plan",
  "currency": "usd"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 9: Budget with more than 2 decimal places
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Precise Budget Plan",
  "budget": 1000.123
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 10: Valid plan creation (baseline)
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Valid Test Plan",
  "description": "This should work",
  "start_date": "2025-06-01",
  "end_date": "2025-06-15",
  "budget": 2500.99,
  "currency": "EUR",
  "is_public": true
}

HTTP 201
[Captures]
valid_plan_id: jsonpath "$.id"
valid_plan_version: jsonpath "$.version"

[Asserts]
jsonpath "$.title" == "Valid Test Plan"
jsonpath "$.budget" == 2500.99

# ===================================================================
# TRAVEL PLAN UPDATE VALIDATION TESTS
# ===================================================================

# Test 11: Update without version (optimistic locking)
PUT {{host}}/api/travel-plans/{{valid_plan_id}}
Content-Type: application/json
{
  "title": "Updated Without Version"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 12: Update with invalid version (zero)
PUT {{host}}/api/travel-plans/{{valid_plan_id}}
Content-Type: application/json
{
  "title": "Updated With Zero Version",
  "version": 0
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 13: Update with negative version
PUT {{host}}/api/travel-plans/{{valid_plan_id}}
Content-Type: application/json
{
  "title": "Updated With Negative Version",
  "version": -1
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# ===================================================================
# LOCATION VALIDATION TESTS  
# ===================================================================

# Test 14: Create location with missing required field (name)
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "address": "Somewhere without name",
  "budget": 100.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 15: Create location with empty name
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "",
  "budget": 100.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 16: Create location with name too long (over 200 characters)
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "This location name is extremely long and exceeds the maximum allowed length of 200 characters for location names. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis.",
  "budget": 100.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 17: Invalid latitude (out of range)
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Invalid Latitude Location",
  "latitude": 91.0,
  "longitude": 2.2945
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 18: Invalid longitude (out of range)
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Invalid Longitude Location",
  "latitude": 48.8584,
  "longitude": 181.0
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 19: Departure before arrival
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Invalid Time Range Location",
  "arrival_date": "2025-06-02T15:00:00Z",
  "departure_date": "2025-06-02T09:00:00Z"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 20: Negative budget for location
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Negative Budget Location",
  "budget": -50.00
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 21: Invalid date format for location
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Invalid Date Format Location",
  "arrival_date": "2025-06-32T25:00:00Z"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 22: Valid location creation (baseline)
POST {{host}}/api/travel-plans/{{valid_plan_id}}/locations
Content-Type: application/json
{
  "name": "Valid Test Location",
  "address": "123 Test Street, Test City",
  "latitude": 48.8584,
  "longitude": 2.2945,
  "arrival_date": "2025-06-02T09:00:00Z",
  "departure_date": "2025-06-02T17:00:00Z",
  "budget": 150.50,
  "notes": "This is a valid location"
}

HTTP 201
[Captures]
valid_location_id: jsonpath "$.id"
valid_location_version: jsonpath "$.version"

[Asserts]
jsonpath "$.name" == "Valid Test Location"
jsonpath "$.visit_order" == 1
jsonpath "$.budget" == 150.50

# ===================================================================
# LOCATION UPDATE VALIDATION TESTS
# ===================================================================

# Test 23: Update location with invalid coordinates
PUT {{host}}/api/locations/{{valid_location_id}}
Content-Type: application/json
{
  "name": "Updated Location",
  "latitude": -91.0,
  "version": {{valid_location_version}}
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Test 24: Update location with invalid time range
PUT {{host}}/api/locations/{{valid_location_id}}
Content-Type: application/json
{
  "arrival_date": "2025-06-02T18:00:00Z",
  "departure_date": "2025-06-02T08:00:00Z",
  "version": {{valid_location_version}}
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# ===================================================================
# EDGE CASE VALIDATION TESTS
# ===================================================================

# Test 25: Create location for non-existent travel plan
POST {{host}}/api/travel-plans/00000000-0000-0000-0000-000000000000/locations
Content-Type: application/json
{
  "name": "Orphan Location"
}

HTTP 404
[Asserts]
jsonpath "$.error" exists

# Test 26: Update non-existent location
PUT {{host}}/api/locations/00000000-0000-0000-0000-000000000000
Content-Type: application/json
{
  "name": "Ghost Location",
  "version": 1
}

HTTP 404
[Asserts]
jsonpath "$.error" exists


# Test 28: Malformed JSON request
POST {{host}}/api/travel-plans
Content-Type: application/json
```json
{
  "title": "Malformed JSON",
  "budget": 1000.00,
  "invalid_json":
}
```

HTTP 400
[Asserts]
jsonpath "$.error" exists

# Test 29: Boundary test - exact limits
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  "budget": 99999999.99,
  "currency": "USD"
}

HTTP 201
[Captures]
boundary_plan_id: jsonpath "$.id"

# Test 30: Coordinates at exact boundaries
POST {{host}}/api/travel-plans/{{boundary_plan_id}}/locations
Content-Type: application/json
{
  "name": "Boundary Location",
  "latitude": -90.0,
  "longitude": 180.0
}

HTTP 201
[Asserts]
jsonpath "$.latitude" == -90.0
jsonpath "$.longitude" == 180.0

# ===================================================================
# CLEANUP
# ===================================================================

# Clean up test data
DELETE {{host}}/api/travel-plans/{{valid_plan_id}}

HTTP 204

DELETE {{host}}/api/travel-plans/{{boundary_plan_id}}

HTTP 204
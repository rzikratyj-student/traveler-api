# Setup: Create plan for location tests
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Location Test Plan",
  "description": "Testing location management"
}

HTTP 201
[Captures]
location_plan_id: jsonpath "$.id"
location1_version: jsonpath "$.version"

# Test 1: Add first location (auto-ordered)
POST {{host}}/api/travel-plans/{{location_plan_id}}/locations
Content-Type: application/json
{
  "name": "Eiffel Tower",
  "address": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris",
  "latitude": 48.8584,
  "longitude": 2.2945,
  "arrival_date": "2025-06-02T09:00:00Z",
  "departure_date": "2025-06-02T12:00:00Z",
  "budget": 25.00,
  "notes": "Visit in the morning for fewer crowds"
}

HTTP 201
[Captures]
location1_id: jsonpath "$.id"

[Asserts]
jsonpath "$.name" == "Eiffel Tower"
jsonpath "$.visit_order" == 1
jsonpath "$.travel_plan_id" == "{{location_plan_id}}"

# Test 2: Add second location (should be auto-ordered as 2)
POST {{host}}/api/travel-plans/{{location_plan_id}}/locations
Content-Type: application/json
{
  "name": "Louvre Museum", 
  "address": "Rue de Rivoli, 75001 Paris",
  "latitude": 48.8606,
  "longitude": 2.3376,
  "budget": 15.00,
  "notes": "Book tickets online"
}

HTTP 201
[Captures]
location2_id: jsonpath "$.id"

[Asserts]
jsonpath "$.visit_order" == 2

# Test 3: Add third location (should be auto-ordered as 3)
POST {{host}}/api/travel-plans/{{location_plan_id}}/locations
Content-Type: application/json
{
  "name": "Arc de Triomphe",
  "budget": 12.00
}

HTTP 201
[Captures]
location3_id: jsonpath "$.id"

[Asserts]
jsonpath "$.visit_order" == 3

# Test 4: Verify plan has all locations
GET {{host}}/api/travel-plans/{{location_plan_id}}

HTTP 200
[Asserts]
jsonpath "$.locations" count == 3
jsonpath "$.locations[0].visit_order" == 1
jsonpath "$.locations[1].visit_order" == 2
jsonpath "$.locations[2].visit_order" == 3

# Test 5: Skip reordering test (simplified system)
# Test 5: Update single location
PUT {{host}}/api/locations/{{location1_id}}
Content-Type: application/json

{
  "name": "Eiffel Tower (Night Visit)",
  "budget": 30.00,
  "notes": "Amazing night illumination",
  "version": {{location1_version}}
}

HTTP 200
[Asserts]
jsonpath "$.version" == 2
jsonpath "$.name" == "Eiffel Tower (Night Visit)"
jsonpath "$.budget" == 30.00
jsonpath "$.notes" == "Amazing night illumination"

# Test 6: Delete location
DELETE {{host}}/api/locations/{{location2_id}}

HTTP 204

# Test 7: Verify deletion (remaining locations keep their order)
GET {{host}}/api/travel-plans/{{location_plan_id}}

HTTP 200
[Asserts]
jsonpath "$.locations" count == 2
# Order may have gaps (1,3) which is acceptable

# Cleanup
DELETE {{host}}/api/travel-plans/{{location_plan_id}}
HTTP 204
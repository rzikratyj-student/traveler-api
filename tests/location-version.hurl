# Create a plan
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "Location version test"
}

HTTP 201
[Captures]
plan_id: jsonpath "$.id"

# Create a location with version 1
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Museum",
  "budget": 50.00,
  "notes": "Book tickets"
}

HTTP 201
[Captures]
location_id: jsonpath "$.id"
initial_version: jsonpath "$.version"
[Asserts]
jsonpath "$.version" == 1

# First client updates the budget
PUT {{host}}/api/locations/{{location_id}}
Content-Type: application/json
{
  "budget": 75.00,
  "version": {{initial_version}}
}

HTTP 200
[Captures]
new_version: jsonpath "$.version"
[Asserts]
jsonpath "$.version" == 2
jsonpath "$.budget" == 75.00
jsonpath "$.notes" == "Book tickets"

# Second client submits a stale version
PUT {{host}}/api/locations/{{location_id}}
Content-Type: application/json
{
  "notes": "Tickets booked!",
  "version": {{initial_version}}
}

HTTP 409
[Asserts]
jsonpath "$.error" contains "Conflict"
jsonpath "$.current_version" == 2

# Confirm that the rejected request changed nothing
GET {{host}}/api/travel-plans/{{plan_id}}

HTTP 200
[Asserts]
jsonpath "$.locations[0].version" == 2
jsonpath "$.locations[0].budget" == 75.00
jsonpath "$.locations[0].notes" == "Book tickets"

# Retry with the current version
PUT {{host}}/api/locations/{{location_id}}
Content-Type: application/json
{
  "notes": "Tickets booked!",
  "version": {{new_version}}
}

HTTP 200
[Asserts]
jsonpath "$.version" == 3
jsonpath "$.budget" == 75.00
jsonpath "$.notes" == "Tickets booked!"

# Missing version must be rejected
PUT {{host}}/api/locations/{{location_id}}
Content-Type: application/json
{
  "notes": "Update without version"
}

HTTP 400
[Asserts]
jsonpath "$.error" contains "Validation error"

# Cleanup
DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 204
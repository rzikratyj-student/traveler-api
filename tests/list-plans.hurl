# Create a plan
POST {{host}}/api/travel-plans
Content-Type: application/json
{
  "title": "List endpoint test"
}

HTTP 201
[Captures]
plan_id: jsonpath "$.id"

# New plan has no locations
GET {{host}}/api/travel-plans
HTTP 200
[Asserts]
# JSONPath filters $[?(...)] return a list in Hurl 7 but a single value
# in Hurl 4-6 and 8, so the body text is checked instead. The API writes
# compact JSON and location_count is the last field of each plan.
body contains "\"id\":\"{{plan_id}}\""
body matches "\"id\":\"{{plan_id}}\"[^}]*\"location_count\":0}"


# Add a location
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Test museum"
}

HTTP 201

# Location count is updated
GET {{host}}/api/travel-plans

HTTP 200
[Asserts]
body matches "\"id\":\"{{plan_id}}\"[^}]*\"location_count\":1}"

# Cleanup
DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 204

# Deleted plan no longer appears
GET {{host}}/api/travel-plans

HTTP 200
[Asserts]
body not contains "{{plan_id}}"
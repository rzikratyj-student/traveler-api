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
jsonpath "$[?(@.id == '{{plan_id}}')].id" == "{{plan_id}}"
jsonpath "$[?(@.id == '{{plan_id}}')].location_count" == 0


# Add a location
POST {{host}}/api/travel-plans/{{plan_id}}/locations
Content-Type: application/json
{
  "name": "Test museum"
}

HTTP 201

# Location count is updated
# Location count is updated
GET {{host}}/api/travel-plans

HTTP 200
[Asserts]
jsonpath "$[?(@.id == '{{plan_id}}')].location_count" == 1

# Cleanup
DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 204

# Deleted plan no longer appears
GET {{host}}/api/travel-plans

HTTP 200
[Asserts]
jsonpath "$[?(@.id == '{{plan_id}}')].id" not exists
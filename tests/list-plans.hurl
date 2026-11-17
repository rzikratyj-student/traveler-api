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
# A filter $[?(...)] always returns a list; "nth 0" takes its element.
# This works the same in Hurl 6 and Hurl 7.
jsonpath "$[?(@.id == '{{plan_id}}')]" count == 1
jsonpath "$[?(@.id == '{{plan_id}}')].id" nth 0 == "{{plan_id}}"
jsonpath "$[?(@.id == '{{plan_id}}')].location_count" nth 0 == 0


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
jsonpath "$[?(@.id == '{{plan_id}}')].location_count" nth 0 == 1

# Cleanup
DELETE {{host}}/api/travel-plans/{{plan_id}}

HTTP 204

# Deleted plan no longer appears
GET {{host}}/api/travel-plans

HTTP 200
[Asserts]
jsonpath "$[?(@.id == '{{plan_id}}')]" count == 0
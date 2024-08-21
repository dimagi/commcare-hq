import jsonschema


def validate_routing_request(request_json):
    schema = {
        "type": "object",
        "properties": {
            "users": {
                "type": "array",
                "items": {
                    "$ref": "#/definitions/location"
                }
            },
            "cases": {
                "type": "array",
                "items": {
                    "$ref": "#/definitions/location"
                }
            }
        },
        "definitions": {
            "location": {
                "type": "object",
                "properties": {
                    "lon": {
                        "type": ["string", "number"],
                        "description": "longitude"
                    },
                    "lat": {
                        "type": ["string", "number"],
                        "description": "latitude"
                    },
                    "id": {
                        "type": "string",
                        "description": "id or pk"
                    }
                },
                "required": ["lon", "lat", "id"]
            }
        },
        "required": ["users", "cases"]
    }
    jsonschema.validate(request_json, schema)

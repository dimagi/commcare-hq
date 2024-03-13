import json
import jsonschema
import requests
from django.conf import settings
from corehq.apps.geospatial.routing_solvers.base import DisbursementAlgorithmSolverInterface


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


def submit_routing_request(request_json):
    # Submits a request to Mapbox Optimize V2 endpoint
    # Docs https://docs.mapbox.com/api/navigation/optimization/#submit-a-routing-problem
    validate_routing_request(request_json)
    payload = generate_request_payload(request_json)
    # Todo; consider using a separte ACCESS_TOKEN for optimize API
    response = requests.post(
        "https://api.mapbox.com/optimized-trips/v2/"
        f"?access_token={settings.MAPBOX_ACCESS_TOKEN}",
        json=payload,
    )

    response.raise_for_status()
    result = json.loads(response.content)
    return result['id']


def generate_request_payload(request_json):
    # Models the user to case assignment optimization problem
    #   as VRP request with users as vehicles and cases as
    #   services.
    return {
        "version": 1,
        "options": {
            "objectives": ["min-schedule-completion-time"]
        },
        "locations": [
            {
                "name": loc["id"],
                "coordinates": [
                    float(loc["lon"]),
                    float(loc["lat"])
                ]
            }
            for loc in (request_json["users"] + request_json["cases"])
        ],
        "vehicles": [
            {
                "name": loc["id"],
                "start_location": loc['id'],
                "end_location": loc['id'],
            }
            for loc in request_json["users"]
        ],
        "services": [
            {
                "name": loc["id"],
                "location": loc["id"]
            }
            for loc in request_json["cases"]
        ]
    }


def routing_status(poll_id):
    # Returns the status of the routing request
    #   False indicates the request is still being processed
    #   If processing is finished, returns a dict of mapping
    response = requests.get(
        f"https://api.mapbox.com/optimized-trips/v2/{poll_id}"
        f"?access_token={settings.MAPBOX_ACCESS_TOKEN}"
    )
    # Todo; handle error responses
    response.raise_for_status()
    if response.status_code != 200:
        return False

    mapping_dict = {}
    # Parse solution
    # https://docs.mapbox.com/api/navigation/optimization/#solution-document
    result = json.loads(response.content)
    for route in result["routes"]:
        user_id = route["vehicle"]
        location_ids = []
        for stop in route["stops"]:
            location_ids.append(stop["location"])
        # First and last stops are user's own location
        location_ids.pop(0)
        location_ids.pop(-1)
        mapping_dict[user_id] = location_ids
    return mapping_dict


class MapboxVRPSolver(DisbursementAlgorithmSolverInterface):

    def solve(self, *args, **kwargs):
        return submit_routing_request(self.request_json), None

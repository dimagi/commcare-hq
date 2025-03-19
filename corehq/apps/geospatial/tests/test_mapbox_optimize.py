import jsonschema
from django.test import SimpleTestCase

from corehq.apps.geospatial.routing_solvers.mapbox_utils import (
    validate_routing_request,
)


class TestMapboxUtils(SimpleTestCase):

    def test_validate_routing_request(self):
        invalid_inputs = [
            {"users": []},
            {"cases": []},
            {
                "users": [
                    {
                        "lon": "76.238907",
                        "lat": "49.232323",
                        # id missing
                    }
                ],
                "cases": [
                    {
                        "lon": "76.238907",
                        "lat": "49.232323",
                        "id": "user1"
                    }
                ]
            }
        ]
        for request in invalid_inputs:
            with self.assertRaises(
                jsonschema.exceptions.ValidationError
            ):
                validate_routing_request(request)

        # Should not fail for correct input
        validate_routing_request(
            {
                "users": [
                    {
                        "lon": "76.238907",
                        "lat": "49.232323",
                        "id": "user1"
                    }
                ],
                "cases": [
                    {
                        "lon": "76.238907",
                        "lat": "49.232323",
                        "id": "user1"
                    }
                ]
            }
        )

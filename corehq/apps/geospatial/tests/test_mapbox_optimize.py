import json
import jsonschema
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase

from corehq.apps.geospatial.routing_solvers.mapbox_optimize import (
    validate_routing_request,
    generate_request_payload,
    submit_routing_request,
)


class TestMapboxRouting(SimpleTestCase):

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

    def test_generate_request_payload(self):
        request = {
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
                    "id": "case1"
                }
            ]
        }

        self.assertEqual(
            generate_request_payload(request),
            {
                "version": 1,
                "options": {
                    "objectives": ["min-schedule-completion-time"]
                },
                "locations": [
                    {"name": "user1", "coordinates": [76.238907, 49.232323]},
                    {"name": "case1", "coordinates": [76.238907, 49.232323]},
                ],
                "vehicles": [
                    {"name": "user1", "start_location": "user1", "end_location": "user1"}
                ],
                "services": [
                    {"name": "case1", "location": "case1"}
                ]
            }
        )

    @patch('corehq.apps.geospatial.routing_solvers.mapbox_optimize.requests')
    def test_submit_request(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_poll_id = 'dsjijsidh33942ksnadk'
        mock_response.content = json.dumps({
            'status': "ok",
            'id': mock_poll_id,
        })
        mock_requests.post.return_value = mock_response
        poll_id = submit_routing_request(
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
        self.assertEqual(poll_id, mock_poll_id)

from django.test import SimpleTestCase

from corehq.apps.geospatial.routing_solvers.ortools import (
    ORToolsRadialDistanceSolver
)


class TestORToolsRadialDistanceSolver(SimpleTestCase):
    # Tests the correctness of the code, not the optimumness of the solution

    def test(self):
        self.assertEqual(
            ORToolsRadialDistanceSolver(
                {
                    "users": [
                        {"id": "New York", "lon": -73.9750671, "lat": 40.7638143},
                        {"id": "Los Angeles", "lon": -117.618932, "lat": 33.045205}
                    ],
                    "cases": [
                        {"id": "New Hampshire", "lon": -71.572395, "lat": 43.193851},
                        {"id": "Phoenix", "lon": -110.475177, "lat": 33.870416},
                    ],
                },
                1000000000,
            ).solve(),
            {'New York': ['New Hampshire'], 'Los Angeles': ['Phoenix']}
        )

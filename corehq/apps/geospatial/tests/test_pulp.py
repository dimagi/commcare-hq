from django.test import SimpleTestCase

from corehq.apps.geospatial.routing_solvers.pulp import (
    RadialDistanceSolver
)
from corehq.apps.geospatial.models import GeoConfig


class TestRadialDistanceSolver(SimpleTestCase):
    # Tests the correctness of the code, not the optimumness of the solution

    def test(self):
        self.assertEqual(
            RadialDistanceSolver(
                {
                    "users": [
                        {"id": "New York", "lon": -73.9750671, "lat": 40.7638143},
                        {"id": "Los Angeles", "lon": -117.618932, "lat": 33.045205}
                    ],
                    "cases": [
                        {"id": "New Hampshire", "lon": -71.572395, "lat": 43.193851},
                        {"id": "Phoenix", "lon": -110.475177, "lat": 33.870416},
                        {"id": "Newark", "lat": 40.78787248247479, "lon": -74.21003634906795},
                        {"id": "NY2", "lat": 40.98704295395249, "lon": -75.21263845406212},
                        {"id": "LA2", "lat": 38.72911676426769, "lon": -114.95862208084543},
                        {"id": "LA3", "lat": 35.39353835883682, "lon": -110.9340138985604},
                        {"id": "Dallas", "lat": 34.4679113819021, "lon": -96.58954660416406},
                        {"id": "Jackson", "lat": 40.55517003526139, "lon": -106.34189549259928},
                    ],
                },
            ).solve(GeoConfig()), (
                None,
                {
                    'New York': ['New Hampshire', 'Newark', 'NY2'],
                    'Los Angeles': ['Phoenix', 'LA2', 'LA3', 'Dallas', 'Jackson']
                }
            )
        )

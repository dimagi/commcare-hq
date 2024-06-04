from django.test import SimpleTestCase

from corehq.apps.geospatial.routing_solvers.pulp import (
    RadialDistanceSolver
)
from corehq.apps.geospatial.models import GeoConfig


class TestRadialDistanceSolver(SimpleTestCase):
    # Tests the correctness of the code, not the optimumness of the solution

    @property
    def _problem_data(self):
        return {
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
        }

    def test_basic(self):
        self.assertEqual(
            RadialDistanceSolver(self._problem_data).solve(GeoConfig()), {
                'assigned': {
                    'New York': ['New Hampshire', 'Newark', 'NY2'],
                    'Los Angeles': ['Phoenix', 'LA2', 'LA3', 'Dallas', 'Jackson']
                }, 'unassigned': []}
        )

    def test_with_max_criteria(self):
        self.assertEqual(
            RadialDistanceSolver(self._problem_data).solve(GeoConfig(max_cases_per_user=4)), {
                'assigned': {
                    'New York': ['New Hampshire', 'Newark', 'NY2', 'Dallas'],
                    'Los Angeles': ['Phoenix', 'LA2', 'LA3', 'Jackson']
                }, 'unassigned': []}
        )

    def test_more_cases_than_is_assignable(self):
        # If max_cases_per_user * n_users < n_cases, that would result in an infeasible solution.
        expected_results = {
            'assigned': [],
            'unassigned': self._problem_data['cases'],
        }
        self.assertEqual(
            RadialDistanceSolver(
                self._problem_data
            ).solve(GeoConfig(max_cases_per_user=2)), expected_results
        )

    def test_too_few_cases_for_minimum_criteria(self):
        expected_results = {
            'assigned': [],
            'unassigned': self._problem_data['cases'],
        }
        self.assertEqual(
            RadialDistanceSolver(
                self._problem_data
            ).solve(GeoConfig(min_cases_per_user=5)), expected_results
        )

    def test_no_cases_is_infeasible_solution(self):
        problem_data = self._problem_data
        problem_data['cases'] = []
        expected_results = {'assigned': [], 'unassigned': []}

        self.assertEqual(
            RadialDistanceSolver(problem_data).solve(GeoConfig()), expected_results
        )

    def test_no_users_is_infeasible_solution(self):
        problem_data = self._problem_data
        problem_data['users'] = []
        expected_results = {
            'assigned': [],
            'unassigned': self._problem_data['cases'],
        }
        self.assertEqual(
            RadialDistanceSolver(problem_data).solve(GeoConfig()), expected_results
        )

    def test_cases_too_far_distance(self):
        expected_results = {
            'assigned': {'New York': [], 'Los Angeles': []},
            'unassigned': self._problem_data['cases'],
        }
        self.assertEqual(
            RadialDistanceSolver(
                self._problem_data
            ).solve(GeoConfig(max_case_distance=1)), expected_results
        )

    def test_massive_distance_disburses_normally(self):
        # This test just shows that, given a big enough radius from the user, the results will look
        # the same as if there was no radius at all
        results_from_normal = RadialDistanceSolver(self._problem_data).solve(GeoConfig())
        results_massive_max_distance = RadialDistanceSolver(self._problem_data).solve(
            GeoConfig(max_case_distance=10000)
        )
        self.assertEqual(
            results_from_normal, results_massive_max_distance
        )

    def test_radial_solver_does_not_take_travel_time_into_account(self):
        results_from_normal = RadialDistanceSolver(self._problem_data).solve(GeoConfig())
        results_with_travel_time = RadialDistanceSolver(self._problem_data).solve(
            GeoConfig(max_case_travel_time=5)
        )
        self.assertEqual(
            results_from_normal, results_with_travel_time
        )

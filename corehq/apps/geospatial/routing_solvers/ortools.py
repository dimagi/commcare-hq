import haversine

import requests

from ortools.linear_solver import pywraplp
from django.conf import settings
from .mapbox_optimize import validate_routing_request


class ORToolsRadialDistanceSolver:
    """
    Solves user-case location assignment based on radial distance

    """

    def __init__(self, request_json, max_route_distance):
        validate_routing_request(request_json)
        self.user_locations = request_json['users']
        self.case_locations = request_json['cases']

    def calculate_distance_matrix(self):
        users = [
            (float(user['lat']), float(user['lon']))
            for user in self.user_locations
        ]
        cases = [
            (float(case['lat']), float(case['lon']))
            for case in self.case_locations
        ]
        return haversine.haversine_vector(cases, users, comb=True)

    def solve(self, print_solution=False):
        # Modelled after https://developers.google.com/optimization/assignment/assignment_teams
        costs = self.calculate_distance_matrix()
        user_count = len(costs)
        case_count = len(costs[0])

        # Solver
        # Create the mip solver with the SCIP backend.
        solver = pywraplp.Solver.CreateSolver("SCIP")

        if not solver:
            return

        # Variables
        # x[i, j] is an array of 0-1 variables, which will be 1
        # if user i is assigned to case j.
        x = {}
        for i in range(user_count):
            for j in range(case_count):
                x[i, j] = solver.IntVar(0, 1, "")

        # Constraints
        # Each user is assigned to at most case_count/user_count
        for i in range(user_count):
            solver.Add(solver.Sum([x[i, j] for j in range(case_count)]) <= int(case_count / user_count) + 1)

        # Each case is assigned to exactly one user.
        for j in range(case_count):
            solver.Add(solver.Sum([x[i, j] for i in range(user_count)]) == 1)

        # Objective
        objective_terms = []
        for i in range(user_count):
            for j in range(case_count):
                objective_terms.append(costs[i][j] * x[i, j])
        solver.Minimize(solver.Sum(objective_terms))

        # Solve
        status = solver.Solve()
        solution = {loc['id']: [] for loc in self.user_locations}
        # Print solution.
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            if print_solution:
                print(f"Total cost = {solver.Objective().Value()}\n")
            for i in range(user_count):
                for j in range(case_count):
                    # Test if x[i,j] is 1 (with tolerance for floating point arithmetic).
                    if x[i, j].solution_value() > 0.5:
                        solution[self.user_locations[i]['id']].append(self.case_locations[j]['id'])
                        if print_solution:
                            print(f"Case {self.case_locations[j]['id']} assigned to "
                                  f"user {self.user_locations[i]['id']}. "
                                  f"Cost: {costs[i][j]}")
        else:
            if print_solution:
                print("No solution found.")
        return solution


class ORToolsRoadNetworkSolver(ORToolsRadialDistanceSolver):
    """
    Solves user-case location assignment based on driving distance
    """

    def calculate_distance_matrix(self):
        # Todo; support more than Mapbox limit by chunking
        if len(self.user_locations + self.case_locations) > 25:
            raise Exception("This is more than Mapbox matrix API limit (25)")

        coordinates = ';'.join([
            f'{loc["lon"]},{loc["lat"]}'
            for loc in self.user_locations + self.case_locations]
        )
        sources = ";".join(map(str, list(range(len(self.user_locations)))))

        url = f'https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coordinates}&{sources}'
        params = {
            'annotations': 'distance',
            'access_token': settings.MAPBOX_ACCESS_TOKEN
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()['distances']

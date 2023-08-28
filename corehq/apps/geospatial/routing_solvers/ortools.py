import numpy as np
from scipy.spatial.distance import cdist

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
        def haversine_distance(coord1, coord2):
            lat1, lon1 = np.radians(coord1)
            lat2, lon2 = np.radians(coord2)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

            distance = 6371 * c  # Earth's radius in kilometers
            return distance

        users = []
        cases = []

        for user in self.user_locations:
            users.append([user['lat'], user['lon']])

        for case in self.case_locations:
            cases.append([case['lat'], case['lon']])

        haversine_matrix = cdist(np.array(users), np.array(cases), haversine_distance)
        return haversine_matrix

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
                            print(f"user {self.user_locations[i]['id']} assigned to case {self.case_locations[j]['id']}." + f" Cost: {costs[i][j]}")
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
            f'{l["lon"]},{l["lat"]}'
            for l in self.user_locations + self.case_locations]
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

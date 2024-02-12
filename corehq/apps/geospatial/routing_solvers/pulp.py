import haversine

import requests
import pulp

from .mapbox_optimize import validate_routing_request
from corehq.apps.geospatial.routing_solvers.base import DisbursementAlgorithmSolverInterface


class RadialDistanceSolver(DisbursementAlgorithmSolverInterface):
    """
    Solves user-case location assignment based on radial distance

    """

    def __init__(self, request_json):
        super().__init__(request_json)

        validate_routing_request(request_json)
        self.user_locations = request_json['users']
        self.case_locations = request_json['cases']

    def calculate_distance_matrix(self, config):
        distance_matrix = []
        for user in self.user_locations:
            user_point = (float(user['lat']), float(user['lon']))
            user_distances = []
            for case in self.case_locations:
                case_point = (float(case['lat']), float(case['lon']))
                user_distances.append(haversine.haversine(case_point, user_point))

            distance_matrix.append(user_distances)

        return distance_matrix

    def solve(self, config, print_solution=False):
        costs = self.calculate_distance_matrix(config)
        user_count = len(costs)
        case_count = len(costs[0])

        # Create a linear programming problem
        problem = pulp.LpProblem("assign_user_cases", pulp.LpMinimize)

        # Define decision variables
        x = {}
        for i in range(user_count):
            for j in range(case_count):
                x[i, j] = pulp.LpVariable(f"x_{i}_{j}", 0, 1, pulp.LpBinary)

        # Add constraints
        for i in range(user_count):
            problem += pulp.lpSum([x[i, j] for j in range(case_count)]) <= int(case_count / user_count) + 1

        for j in range(case_count):
            problem += pulp.lpSum([x[i, j] for i in range(user_count)]) == 1

        # Define the objective function
        objective_terms = [costs[i][j] * x[i, j] for i in range(user_count) for j in range(case_count)]
        problem += pulp.lpSum(objective_terms)

        # Solve the problem
        problem.solve()

        solution = {loc['id']: [] for loc in self.user_locations}

        # Process the solution
        if pulp.LpStatus[problem.status] == "Optimal":
            if print_solution:
                print(f"Total cost = {pulp.value(problem.objective)}\n")
            for i in range(user_count):
                for j in range(case_count):
                    if pulp.value(x[i, j]) > 0.5:
                        solution[self.user_locations[i]['id']].append(self.case_locations[j]['id'])
                        if print_solution:
                            print(f"Case {self.case_locations[j]['id']} assigned to "
                                  f"user {self.user_locations[i]['id']}. "
                                  f"Cost: {costs[i][j]}")
        else:
            if print_solution:
                print("No solution found.")
        return None, solution


class RoadNetworkSolver(RadialDistanceSolver):
    """
    Solves user-case location assignment based on driving distance
    """

    def calculate_distance_matrix(self, config):
        # Todo; support more than Mapbox limit by chunking
        if len(self.user_locations + self.case_locations) > 25:
            raise Exception("This is more than Mapbox matrix API limit (25)")

        coordinates = ';'.join([
            f'{loc["lon"]},{loc["lat"]}'
            for loc in self.user_locations + self.case_locations]
        )
        sources_count = len(self.user_locations)
        destinations_count = len(self.case_locations)

        sources = ";".join(map(str, list(range(sources_count))))
        destinations = ";".join(map(str, list(range(sources_count, sources_count + destinations_count))))

        url = f'https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coordinates}'
        params = {
            'sources': sources,
            'destinations': destinations,
            'annotations': 'distance',
            'access_token': config.plaintext_api_token,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()['distances']

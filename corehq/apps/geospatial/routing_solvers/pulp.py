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

    def solve(self, config):
        costs = self.calculate_distance_matrix(config)
        user_count = len(costs)
        case_count = len(costs[0])

        # Define decision variables
        decision_variables = self.get_decision_variables(x_dim=user_count, y_dim=case_count)

        # Create a linear programming problem
        problem = pulp.LpProblem("assign_user_cases", sense=pulp.LpMinimize)

        # Add constraints
        problem = self.add_user_case_assignment_constraint(
            lp_problem=problem,
            decision_variables=decision_variables,
            user_count=user_count,
            case_count=case_count,
            min_cases=config.min_cases_per_user,
            max_cases=config.max_cases_per_user,
        )
        problem = self.add_case_owner_constraint(
            lp_problem=problem,
            decision_variables=decision_variables,
            user_count=user_count,
            case_count=case_count,
        )

        # Define the objective function
        objective_terms = [
            costs[i][j] * decision_variables[i, j]
            for i in range(user_count) for j in range(case_count)
        ]
        problem += pulp.lpSum(objective_terms)

        # Solve the problem
        problem.solve()

        # Process the solution
        if pulp.LpStatus[problem.status] == "Optimal":
            solution = {loc['id']: [] for loc in self.user_locations}

            for i in range(user_count):
                for j in range(case_count):
                    if pulp.value(decision_variables[i, j]) > 0.5:
                        solution[self.user_locations[i]['id']].append(self.case_locations[j]['id'])
            return None, solution

        return None, None

    @staticmethod
    def get_decision_variables(x_dim, y_dim):
        matrix = {}
        for i in range(x_dim):
            for j in range(y_dim):
                matrix[i, j] = pulp.LpVariable(f"x_{i}_{j}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        return matrix

    @staticmethod
    def add_user_case_assignment_constraint(
        lp_problem, decision_variables, user_count, case_count, min_cases=None, max_cases=None
    ):
        # This constrain enforces the min/max amount of cases that could be assigned to each user,
        # with the default being the cases split equally between users.
        max_constraint = int(case_count / user_count) + 1
        min_constraint = 0

        if min_cases:
            min_constraint = min_cases
        if max_cases:
            max_constraint = max_cases

        for i in range(user_count):
            lp_problem += pulp.lpSum([decision_variables[i, j] for j in range(case_count)]) <= max_constraint
            lp_problem += pulp.lpSum([decision_variables[i, j] for j in range(case_count)]) >= min_constraint

        return lp_problem

    @staticmethod
    def add_case_owner_constraint(lp_problem, decision_variables, user_count, case_count):
        # This constraint ensures that every case can only ever have one user assigned to it
        for j in range(case_count):
            lp_problem += pulp.lpSum([decision_variables[i, j] for i in range(user_count)]) == 1
        return lp_problem


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

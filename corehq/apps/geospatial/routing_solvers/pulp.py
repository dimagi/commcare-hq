import haversine
import requests
import pulp
import copy

from .mapbox_utils import validate_routing_request
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

        return distance_matrix, None

    def solve(self, config, print_solution=False):
        distance_costs, duration_costs = self.calculate_distance_matrix(config)

        if not distance_costs:
            return self.solution_results(assigned=[], unassigned=self.case_locations)

        user_count = len(distance_costs)
        case_count = len(distance_costs[0])

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
            distance_costs[i][j] * decision_variables[i, j]
            for i in range(user_count) for j in range(case_count)
        ]
        problem += pulp.lpSum(objective_terms)

        # Solve the problem
        problem.solve()

        assigned_cases = []
        unassigned_cases = copy.deepcopy(self.case_locations)

        # Process the solution
        if pulp.LpStatus[problem.status] == "Optimal":
            solution = {loc['id']: [] for loc in self.user_locations}

            for i in range(user_count):
                for j in range(case_count):
                    if pulp.value(decision_variables[i, j]) > 0.5:
                        case_is_valid = self.is_valid_user_case(
                            config,
                            distance_to_case=distance_costs[i][j],
                            travel_secs_to_case=None if duration_costs is None else duration_costs[i][j],
                        )
                        if case_is_valid:
                            solution[self.user_locations[i]['id']].append(self.case_locations[j]['id'])
                            unassigned_cases.remove(self.case_locations[j])
            assigned_cases = solution

        return self.solution_results(assigned=assigned_cases, unassigned=unassigned_cases)

    @staticmethod
    def solution_results(assigned, unassigned):
        return {"assigned": assigned, "unassigned": unassigned}

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
        max_constraint = max_cases or int(case_count / user_count) + 1
        min_constraint = min_cases or 0

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

    @staticmethod
    def is_valid_user_case(config, distance_to_case=None, travel_secs_to_case=None):
        should_check_distance = distance_to_case and config.max_case_distance
        if should_check_distance and distance_to_case > config.max_case_distance:
            return False

        should_check_duration = travel_secs_to_case and config.max_case_travel_time
        if should_check_duration and travel_secs_to_case > config.max_travel_time_seconds:
            return False

        return True


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

        url = f'https://api.mapbox.com/directions-matrix/v1/mapbox/{config.travel_mode}/{coordinates}'

        if config.max_case_travel_time:
            annotations = "distance,duration"
        else:
            annotations = "distance"

        params = {
            'sources': sources,
            'destinations': destinations,
            'annotations': annotations,
            'access_token': config.plaintext_api_token,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        return self.sanitize_response(response.json())

    def sanitize_response(self, response):
        distances_km = self._convert_m_to_km(response['distances'])
        durations_sec = response.get('durations', None)
        return distances_km, durations_sec

    @staticmethod
    def _convert_m_to_km(distances_m):
        distances_km = []
        for row in distances_m:
            distances_km.append(
                [value_m / 1000 for value_m in row]
            )
        return distances_km

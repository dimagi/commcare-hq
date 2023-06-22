import requests
import geopandas as gpd

from geopy import distance
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from django.conf import settings
from .mapbox_optimize import validate_routing_request


class ORToolsRadialDistanceSolver:
    """
    Solves user-case location assignment based on radial distance
        supports max_route_distance constraint.
    """

    def __init__(self, request_json, max_route_distance):
        validate_routing_request(request_json)
        self.user_locations = request_json['users']
        self.case_locations = request_json['cases']
        self.max_route_distance = max_route_distance

    def calculate_distance_matrix(self):
        locations = self.user_locations + self.case_locations
        gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(
                [l['lon'] for l in locations],
                [l['lat'] for l in locations]
            )
        )
        distances = []
        for i, row1 in gdf.iterrows():
            row_distances = []
            for j, row2 in gdf.iterrows():
                dist = distance.distance(
                    (row1.geometry.y, row1.geometry.x), (row2.geometry.y, row2.geometry.x)
                ).meters
                row_distances.append(dist)
            distances.append(row_distances)

        return distances

    def create_data_model(self):
        user_count = len(self.user_locations)
        data = {}
        data['distance_matrix'] = self.calculate_distance_matrix()
        data['num_vehicles'] = user_count
        data['starts'] = [i for i in range(user_count)]
        data['ends'] = [i for i in range(user_count)]
        return data

    def solve(self, print_routes=False):
        # Instantiate the data problem.
        data = self.create_data_model()

        # Create the routing index manager.
        manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                               data['num_vehicles'], data['starts'],
                                               data['ends'])

        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)

        # Create and register a transit callback.
        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            # Convert from routing variable Index to distance matrix NodeIndex.
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data['distance_matrix'][from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)

        # Define cost of each arc.
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add Distance constraint.
        dimension_name = 'Distance'
        routing.AddDimension(
            transit_callback_index,
            0,
            self.max_route_distance,
            True,
            dimension_name)
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(100)

        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC)

        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            # Todo; custom exception type
            raise Exception("No Solution Found")
        # Print solution on console.
        if print_routes:
            self.print_solution(data, manager, routing, solution)
        return self.user_to_case_map(routing, solution)

    def print_solution(self, data, manager, routing, solution):
        max_route_distance = 0
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
            route_distance = 0
            while not routing.IsEnd(index):
                plan_output += ' {} -> '.format(manager.IndexToNode(index))
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id)
            plan_output += '{}\n'.format(manager.IndexToNode(index))
            plan_output += 'Distance of the route: {}m\n'.format(route_distance)
            print(plan_output)
            max_route_distance = max(route_distance, max_route_distance)
        print('Maximum of the route distances: {}m'.format(max_route_distance))

    def user_to_case_map(self, routing, solution):
        routes = []
        for user_index in range(len(self.user_locations)):
            index = routing.Start(user_index)
            route = []
            while not routing.IsEnd(index):
                index = solution.Value(routing.NextVar(index))
                route.append(index)
            route.pop(-1)  # remove end location
            routes.append(route)
        ret = {}
        for i, user in enumerate(self.user_locations):
            ret[user['id']] = [
                self.case_locations[case_index - len(self.user_locations)]['id']
                for case_index in routes[i]
            ]
            routes[i]
        return ret


class ORToolsRoadNetworkSolver(ORToolsRadialDistanceSolver):
    """
    Solves user-case location assignment based on driving distance
    """

    def calculate_distance_matrix(self):
        # Todo; support more than Mapbox limit by chunking
        if len(self.user_locations + self.case_locations) > 25:
            raise Exception("This is more than Mapbox matrix API limit")

        coordinates = ';'.join([
            f'{l["lon"]},{l["lat"]}'
            for l in self.user_locations + self.case_locations]
        )

        url = f'https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coordinates}'
        params = {
            'annotations': 'distance',
            'access_token': settings.MAPBOX_ACCESS_TOKEN
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()['distances']

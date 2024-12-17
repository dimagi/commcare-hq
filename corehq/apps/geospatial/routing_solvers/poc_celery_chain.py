import math
import time
from collections import namedtuple

from jsonobject.exceptions import BadValueError
from sklearn.cluster import KMeans
import numpy as np

from corehq.apps.es.case_search import case_property_missing, CaseSearchES, wrap_case_search_hit
from corehq.apps.es.users import missing_or_empty_user_data_property, UserES
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.routing_solvers.pulp import RadialDistanceSolver
from corehq.apps.geospatial.utils import get_geo_case_property, get_geo_user_property

from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.geopoint import GeoPoint
from dimagi.utils.couch.database import iter_docs

CaseIdList = list[str]
UserIdList = list[str]
Coordinate = namedtuple('Coordinate', 'lat lon')
CoordinatesDict = dict[str, list[Coordinate]]  # e.g. {'users': [(33.9, 18.4)]}

QUERY_CHUNK_SIZE = 10000


def create_clusters(users, cases, n_clusters: int) -> dict[int, CoordinatesDict]:
    """
    Uses k-means clustering to return a dictionary of ``n_clusters``
    number of clusters of users and cases based on their coordinates.
    """
    n_users = len(users)
    locations = users + cases
    coordinates = np.array([[loc['lat'], loc['lon']] for loc in locations])
    kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(coordinates)
    clusters = {i: {'users': [], 'cases': []} for i in range(n_clusters)}
    for idx, label in enumerate(kmeans.labels_):
        if idx < n_users:
            clusters[label]['users'].append(users[idx])
        else:
            clusters[label]['cases'].append(cases[idx - n_users])
    return clusters


def get_geo_location(case, geo_case_property):
    geo_point = case.get_case_property(geo_case_property)
    return _get_location_from_string(geo_point)


def _get_location_from_string(data):
    try:
        geo_point = GeoPoint.from_string(data, flexible=True)
        return {"lat": geo_point.latitude, "lng": geo_point.longitude}
    except BadValueError:
        return None


def get_users_with_gps(domain):
    location_prop_name = get_geo_user_property(domain)
    query = (
        UserES()
        .domain(domain)
        .mobile_users()
        .NOT(missing_or_empty_user_data_property(location_prop_name))
        .fields(['location_id', '_id'])
    )

    user_ids = []
    for user_doc in query.run().hits:
        user_ids.append(user_doc['_id'])

    users = map(CouchUser.wrap_correctly, iter_docs(CommCareUser.get_db(), user_ids))
    user_data = []
    for user in users:
        location = user.get_user_data(domain).get(location_prop_name, '')
        coordinates = _get_location_from_string(location) if location else None
        if coordinates:
            user_data.append(
                {
                    'id': user.user_id,
                    'lon': coordinates['lng'],
                    'lat': coordinates['lat'],
                }
            )
    return user_data


def get_cases(domain, offset):
    geo_case_property = get_geo_case_property(domain)

    query = CaseSearchES().domain(domain).size(QUERY_CHUNK_SIZE).start(offset)
    query = query.NOT(case_property_missing(geo_case_property))

    cases = []
    for row in query.run().raw['hits'].get('hits', []):
        display = CaseDisplayES(
            row['_source']
        )
        case = wrap_case_search_hit(row)
        coordinates = get_geo_location(case, geo_case_property)
        if coordinates:
            cases.append({
                'id': display.case_id,
                'lon': coordinates['lng'],
                'lat': coordinates['lat'],
                # 'case_name': display.case_name,
                # 'gps_point': coordinates,
                # 'case_link': display.case_link,
            })
    return cases


def run():
    domain = 'local-1'

    users = get_users_with_gps(domain)
    print("Total Users", len(users))

    geo_case_property = get_geo_case_property(domain)
    total_cases = CaseSearchES().domain(domain).NOT(case_property_missing(geo_case_property)).count()
    print("Total Cases", total_cases)

    batch_count = math.ceil(total_cases / QUERY_CHUNK_SIZE)
    cases = []

    for i in range(batch_count):
        print(f"Fetch Cases: Processing Batch {i+1} of {batch_count}...")
        cases.extend(
            get_cases(domain, offset=i*QUERY_CHUNK_SIZE)
        )

    print("Creating clusters... Be patient...")
    start_time = time.time()
    chunk_size = 10000
    n_clusters = max(len(users), len(cases)) // chunk_size + 1
    clusters = create_clusters(
       users,
       cases,
       n_clusters,
    )
    print(f"Time for creating clusters: {time.time() - start_time}")

    start_time = time.time()
    assignments = []
    config = GeoConfig.objects.get(domain=domain)
    for cluster_id in range(n_clusters):
        users_chunk = clusters[cluster_id]['users']
        cases_chunk = clusters[cluster_id]['cases']
        if users_chunk and cases_chunk:
            print(f"Solving disbursement for cluster {cluster_id}...")
            solver = RadialDistanceSolver(clusters[cluster_id])
            results = solver.solve(config)
            assignments.append(results)
            print(f"Completed disbursement for cluster {cluster_id}")
        elif users_chunk:
            print('No cases available for mobile workers in cluster_id {}'.format(cluster_id))
        elif cases_chunk:
            print('No mobile workers available for cases in cluster_id {}'.format(cluster_id))
    print(f"Total Time for solving disbursement: {time.time() - start_time}")
    return assignments


run()

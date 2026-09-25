import boto3
import json
import time

#! UNCOMMENT to create clusters locally. This will require the installation of the scikit-learn and numpy libraries
# import numpy as np
# from sklearn.cluster import KMeans

from settings import (
    LAMBDA_AWS_ACCESS_KEY_ID,
    LAMBDA_AWS_SECRET_ACCESS_KEY,
    LAMBDA_AWS_FUNC_REGION,
    LAMBDA_AWS_CREATE_CLUSTERS_FUNC_NAME,
)

from django.core.management import BaseCommand

from jsonobject.exceptions import BadValueError

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_property_missing, wrap_case_search_hit
from corehq.apps.es.users import missing_or_empty_user_data_property
from corehq.apps.geospatial.utils import get_geo_case_property, get_geo_user_property
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.util.log import with_progress_bar
from couchforms.geopoint import GeoPoint
from dimagi.utils.couch.database import iter_docs


ES_QUERY_CHUNK_SIZE = 10_000


class Command(BaseCommand):
    help = ('(POC) Test performance of k-means clustering using AWS Lambda '
            'function')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--cluster_chunk_size', required=False, default=10000, type=int)
        parser.add_argument('--limit_cases', required=False, type=int, help="limits the number of cases to fetch")
        parser.add_argument('--limit_users', required=False, type=int, help="limits the number of users to fetch")

    def handle(self, *args, **options):
        domain = options['domain']
        cluster_chunk_size = options['cluster_chunk_size']
        limit_cases = options['limit_cases']
        limit_users = options['limit_users']

        start_time = time.time()
        gps_users_data = self.get_users_with_gps(domain, limit_users)
        print(f"Time taken for fetching {len(gps_users_data)} users: {round(time.time() - start_time, 2)}s")

        geo_case_property = get_geo_case_property(domain)
        total_cases = CaseSearchES().domain(domain).NOT(case_property_missing(geo_case_property)).count()

        start_time = time.time()
        cases_data = self.get_cases_with_gps(domain, geo_case_property, limit_cases)
        print(f"Time taken for fetching {total_cases} cases: {round(time.time() - start_time, 2)}s")

        start_time = time.time()
        n_clusters = max(len(gps_users_data), len(cases_data)) // cluster_chunk_size + 1
        print(f"Creating {n_clusters} clusters for {len(gps_users_data)} users and {len(cases_data)} cases...")
        # clusters = self.create_clusters_locally(cases_data, gps_users_data, n_clusters)
        clusters = self.create_clusters(cases_data, gps_users_data, n_clusters)
        print(f"Time taken for creating clusters: {round(time.time() - start_time, 2)}s")
        empty_cluster_count = self.check_for_empty_clusters(clusters)
        print(f"Number of empty case clusters with no users: {empty_cluster_count['users']}")
        print(f"Number of empty user clusters with no cases: {empty_cluster_count['cases']}")

    def get_users_with_gps(self, domain, limit_users):
        """Mostly copied over from corehq.apps.geospatial.views.get_users_with_gps"""
        location_prop_name = get_geo_user_property(domain)
        from corehq.apps.es import UserES
        query = (
            UserES()
            .domain(domain)
            .mobile_users()
            .NOT(missing_or_empty_user_data_property(location_prop_name))
            .fields(['location_id', '_id'])
        )
        if limit_users:
            query = query.size(limit_users)

        user_ids = []
        for user_doc in query.run().hits:
            user_ids.append(user_doc['_id'])

        users = map(CouchUser.wrap_correctly, iter_docs(CommCareUser.get_db(), user_ids))
        users_data = []
        for user in users:
            location = user.get_user_data(domain).get(location_prop_name, '')
            coordinates = self._get_location_from_string(location) if location else None
            if coordinates:
                users_data.append({
                    'id': user.user_id,
                    'lon': coordinates['lng'],
                    'lat': coordinates['lat'],
                })
        return users_data

    def _get_location_from_string(self, data):
        try:
            geo_point = GeoPoint.from_string(data, flexible=True)
            return {"lat": float(geo_point.latitude), "lng": float(geo_point.longitude)}
        except BadValueError:
            return None

    def get_cases_with_gps(self, domain, geo_case_property, limit_total_cases):
        query = CaseSearchES().domain(domain).size(ES_QUERY_CHUNK_SIZE)
        query = query.NOT(case_property_missing(geo_case_property))

        cases_data = []
        total_cases = limit_total_cases if limit_total_cases else query.count()
        for row in with_progress_bar(query.scroll(), total_cases, prefix="Fetching cases"):
            case = wrap_case_search_hit(row)
            coordinates = self.get_case_geo_location(case, geo_case_property)
            if coordinates:
                cases_data.append({
                    'id': case.case_id,
                    'lon': coordinates['lng'],
                    'lat': coordinates['lat'],
                })
            if limit_total_cases and len(cases_data) >= limit_total_cases:
                break
        return cases_data

    def get_case_geo_location(self, case, geo_case_property):
        geo_point = case.get_case_property(geo_case_property)
        return self._get_location_from_string(geo_point)

    def create_clusters(self, cases, users, n_clusters):
        # Send a request to an AWS Lambda function to do k-means clustering
        # A Celery task will be used to loop through all clusters and solve them
        payload = {
            'cases': cases,
            'users': users,
            'n_clusters': n_clusters,
        }

        # TODO: Insert below constants into localsettings with appropriate values
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=LAMBDA_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=LAMBDA_AWS_SECRET_ACCESS_KEY,
            region_name=LAMBDA_AWS_FUNC_REGION
        )
        response = lambda_client.invoke(
            FunctionName=LAMBDA_AWS_CREATE_CLUSTERS_FUNC_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        response_payload = json.loads(response['Payload'].read())
        if response_payload['statusCode'] != 200:
            print("Error while creating clusters:", response_payload['message'])
            return {}
        clusters = json.loads(response_payload['clusters'])
        return clusters

    #! UNCOMMENT to create clusters locally. This will require the installation
    #! of the scikit-learn and numpy libraries
    # def create_clusters_locally(self, cases, users, n_clusters):
    #     n_users = len(users)
    #     locations = users + cases
    #     coordinates = np.array([[loc['lat'], loc['lon']] for loc in locations])
    #     kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(coordinates)
    #     clusters = {i: {'users': [], 'cases': []} for i in range(n_clusters)}
    #     for idx, label in enumerate(kmeans.labels_):
    #         if idx < n_users:
    #             clusters[label]['users'].append(users[idx])
    #         else:
    #             clusters[label]['cases'].append(cases[idx - n_users])
    #     return clusters

    def check_for_empty_clusters(self, clusters):
        empty_cluster_counts = {
            'users': 0,
            'cases': 0
        }
        for cluster in clusters.values():
            if not cluster['users']:
                empty_cluster_counts['users'] += 1
            elif not cluster['cases']:
                empty_cluster_counts['cases'] += 1
        return empty_cluster_counts

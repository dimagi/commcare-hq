import math
import time
from itertools import islice

from django.core.management import BaseCommand

from jsonobject.exceptions import BadValueError
from sklearn.cluster import KMeans
import numpy as np

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_property_missing, wrap_case_search_hit
from corehq.apps.es.users import missing_or_empty_user_data_property
from corehq.apps.geospatial.utils import get_geo_case_property, get_geo_user_property
from corehq.apps.geospatial.tasks import clusters_disbursement_task
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.geopoint import GeoPoint
from dimagi.utils.couch.database import iter_docs

ES_QUERY_CHUNK_SIZE = 10000


class Command(BaseCommand):
    help = ('(POC) Test performance of road network disbursement algorithm using k-cluster and '
            'sequential approach for mapbox API limit (60 requests/min)')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--cluster_chunk_size', required=False, default=10000, type=int)
        parser.add_argument('--dry_run', action='store_true', help="skips running the disbursement task")
        parser.add_argument(
            '--cluster_solve_percent',
            required=False,
            default=10,
            type=int,
            help="solves disbursement for percent of clusters specified",
        )
        parser.add_argument('--limit_memory', required=False, type=int, help="limits memory usage to size in MB")

    def handle(self, *args, **options):
        limit_memory = options.get('limit_memory')
        if limit_memory:
            set_max_memory(limit_memory)

        domain = options['domain']
        cluster_chunk_size = options['cluster_chunk_size']
        print(f"Cluster chunk size: {cluster_chunk_size}")

        geo_case_property = get_geo_case_property(domain)

        gps_users_data = self.get_users_with_gps(domain)
        print(f"Total GPS Mobile workers: {len(gps_users_data)}")

        total_cases = CaseSearchES().domain(domain).NOT(case_property_missing(geo_case_property)).count()
        print(f"Total GPS Cases: {total_cases}")
        cases_data = []
        batch_count = math.ceil(total_cases / ES_QUERY_CHUNK_SIZE)
        for i in range(batch_count):
            print(f"Fetching Cases: Processing Batch {i + 1} of {batch_count}...")
            cases_data.extend(
                self.get_cases_with_gps(domain, geo_case_property, offset=i * ES_QUERY_CHUNK_SIZE)
            )
        print("All cases fetched successfully")

        start_time = time.time()
        n_clusters = max(len(gps_users_data), len(cases_data)) // cluster_chunk_size + 1
        print(f"Creating {n_clusters} clusters for {len(gps_users_data)} users and {len(cases_data)} cases...")
        clusters = self.create_clusters(gps_users_data, cases_data, n_clusters)
        print(f"Time taken for creating clusters: {time.time() - start_time}")

        if not options['dry_run']:
            cluster_solve_percent = options['cluster_solve_percent']
            number_of_clusters_to_disburse = int(cluster_solve_percent / 100 * len(clusters))
            clusters_to_disburse = dict(islice(clusters.items(), number_of_clusters_to_disburse))
            clusters_disbursement_task.delay(domain, clusters_to_disburse)

    def get_users_with_gps(self, domain):
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

        user_ids = []
        for user_doc in query.run().hits:
            user_ids.append(user_doc['_id'])

        users = map(CouchUser.wrap_correctly, iter_docs(CommCareUser.get_db(), user_ids))
        users_data = []
        for user in users:
            location = user.get_user_data(domain).get(location_prop_name, '')
            coordinates = self._get_location_from_string(location) if location else None
            if coordinates:
                users_data.append(
                    {
                        'id': user.user_id,
                        'lon': coordinates['lng'],
                        'lat': coordinates['lat'],
                    }
                )
        return users_data

    def _get_location_from_string(self, data):
        try:
            geo_point = GeoPoint.from_string(data, flexible=True)
            return {"lat": geo_point.latitude, "lng": geo_point.longitude}
        except BadValueError:
            return None

    def get_cases_with_gps(self, domain, geo_case_property, offset):
        query = CaseSearchES().domain(domain).size(ES_QUERY_CHUNK_SIZE).start(offset)
        query = query.NOT(case_property_missing(geo_case_property))

        cases_data = []
        for row in query.run().raw['hits'].get('hits', []):
            case = wrap_case_search_hit(row)
            coordinates = self.get_case_geo_location(case, geo_case_property)
            if coordinates:
                cases_data.append({
                    'id': case.case_id,
                    'lon': coordinates['lng'],
                    'lat': coordinates['lat'],
                })
        return cases_data

    def get_case_geo_location(self, case, geo_case_property):
        geo_point = case.get_case_property(geo_case_property)
        return self._get_location_from_string(geo_point)

    def create_clusters(self, users, cases, n_clusters):
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
        for key in clusters.keys():
            print(f"cluster index: {key}, users: {len(clusters[key]['users'])},"
                  f" cases: {len(clusters[key]['cases'])}")
        return clusters


# Can be used to set max memory for the process (used for low memory machines, like india django server)
# Example: 800 MB set_max_memory(1024 * 1000 * 800)
def set_max_memory(size_in_mb):  # size (in bytes)
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1000 * size_in_mb, hard))

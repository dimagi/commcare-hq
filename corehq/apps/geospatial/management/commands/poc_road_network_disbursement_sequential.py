import math

from django.core.management import BaseCommand

from jsonobject.exceptions import BadValueError

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_property_missing, wrap_case_search_hit
from corehq.apps.es.users import missing_or_empty_user_data_property
from corehq.apps.geospatial.utils import get_geo_case_property, get_geo_user_property
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.geopoint import GeoPoint
from dimagi.utils.couch.database import iter_docs

ES_QUERY_CHUNK_SIZE = 10000


class Command(BaseCommand):
    help = ('(POC) Test performance of road network disbursement algorithm using k-cluster and '
            'sequential approach for mapbox API limit (60 requests/min)')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--cluster_chunk_size', required=False, default=10000)

    def handle(self, *args, **options):
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

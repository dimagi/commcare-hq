from contextlib import contextmanager
from random import random, seed
from unittest.mock import patch
from uuid import uuid4

from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.test_case_search_es import BaseCaseSearchTest
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.util.test_utils import flag_enabled
from couchforms.geopoint import GeoPoint

from ..es import AGG_NAME, get_geohashes

GEO_CASE_PROPERTY = 'gps_point'  # TODO: Fetch this value

TOP_LEFT = '48.90 2.30'  # 48.90 lat is above 48.80 lat
BOTTOM_RIGHT = '48.80 2.40'


class TestGetGeohashes(BaseCaseSearchTest):

    @contextmanager
    def create_cases(self, num_cases):
        seed(b'quarante-deux')
        input_cases = (
            {'_id': str(uuid4()), GEO_CASE_PROPERTY: somewhere_in_paris()}
            for __ in range(num_cases)
        )
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, input_cases)
        yield

    # test setup:
    @flag_enabled('USH_CASE_CLAIM_UPDATES')  # reqd for adding geopoint_value
    @patch('corehq.apps.geospatial.es.MAX_DOC_COUNT', 10)
    @patch('corehq.pillows.case_search.get_gps_properties',
           return_value={GEO_CASE_PROPERTY})
    # patching to avoid unwanted code paths:
    @patch('casexml.apps.phone.restore_caching.'
           'get_loadtest_factor_for_restore_cache_key', return_value=1)
    @patch('corehq.form_processor.submission_post.report_case_usage')
    @patch('corehq.motech.repeaters.signals._create_repeat_records')
    def test_aggregation(self, *args):
        top_left = GeoPoint.from_string(TOP_LEFT, flexible=True)
        bottom_left = GeoPoint.from_string(BOTTOM_RIGHT, flexible=True)
        with self.create_cases(11):

            es_query, precision = get_geohashes(
                self.domain,
                field=GEO_CASE_PROPERTY,
                top_left=top_left,
                bottom_right=bottom_left,
                precision=1,
            )
            self.assertEqual(precision, 1)

            # elasticsearch2.exceptions.RequestError: TransportError(400, 'sear
            # ch_phase_execution_exception', 'failed to parse [geo_bbox] query.
            # could not find [geo_point] field [gps_point]')
            self.assertEqual(es_query.count(), 11)

            queryset = es_query.run()
            self.assertEqual(
                queryset.raw['aggregations'][AGG_NAME]['buckets'],
                [],  # TODO: Why?!
            )

    # def test_finding_precision_11(self):
    #     with self.create_cases(11):
    #         es_query, precision = get_geohashes(
    #             DOMAIN,
    #             field=GEO_CASE_PROPERTY,
    #         )
    #         self.assertLess(precision, 6)
    #         self.assertEqual(es_query.count(), 1)
    #
    # def test_finding_precision_11k(self):
    #     with self.create_cases(11_000):
    #         es_query, precision = get_geohashes(
    #             DOMAIN,
    #             field=GEO_CASE_PROPERTY,
    #         )
    #         self.assertLess(precision, 6)
    #         self.assertGreater(es_query.count(), 1)
    #
    #         total = 0
    #         # TODO: This is not the best API
    #         for geohash in es_query.run().aggregation(AGG_NAME):
    #             # TODO: Count the cases
    #             pass
    #         self.assertEqual(total, 11_000)


def somewhere_in_paris():
    random_lat = random() / 10 - 0.05  # -0.05 <= random_lat < 0.05
    random_lon = random() / 10 - 0.05
    lat = 48.85 + random_lat
    lon = 2.35 + random_lon
    return f'{lat} {lon}'

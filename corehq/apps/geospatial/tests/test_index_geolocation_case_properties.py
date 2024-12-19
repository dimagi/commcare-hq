from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.management.commands.index_geolocation_case_properties import index_case_docs
from corehq.apps.geospatial.models import GeoConfig


@es_test(requires=[case_search_adapter], setup_class=True)
class TestGetFormCases(TestCase):
    domain = 'foobar'
    primary_case_type = 'primary'
    secondary_case_type = 'secondary'
    gps_prop_name = 'gps_coordinates'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        factory = CaseFactory(cls.domain)
        case1 = factory.create_case(
            case_name='foo',
            case_type=cls.primary_case_type,
            update={cls.gps_prop_name: '1.1 2.2'},
        )
        case2 = factory.create_case(
            case_name='bar',
            case_type=cls.primary_case_type,
            update={cls.gps_prop_name: '3.3 4.4'},
        )
        case3 = factory.create_case(
            case_name='other',
            case_type=cls.secondary_case_type,
            update={cls.gps_prop_name: '5.5 6.6'},
        )
        case4 = factory.create_case(
            case_name='no_props',
            case_type=cls.primary_case_type,
        )
        case_search_adapter.bulk_index([case1, case2, case3, case4], refresh=True)
        cls.geo_config = GeoConfig.objects.create(
            domain=cls.domain,
            case_location_property_name=cls.gps_prop_name
        )
        cls.addClassCleanup(cls.geo_config.delete)

    def test_has_cases_to_index(self):
        query = case_query_for_missing_geopoint_val(self.domain, self.gps_prop_name, self.primary_case_type)
        case_count = query.count()
        self.assertEqual(case_count, 2)

    def test_cases_correctly_indexed(self):
        index_case_docs(self.domain, case_type=self.secondary_case_type)
        manager.index_refresh(case_search_adapter.index_name)
        query = case_query_for_missing_geopoint_val(self.domain, self.gps_prop_name, self.secondary_case_type)
        case_count = query.count()
        self.assertEqual(case_count, 0)
        doc = (
            CaseSearchES()
            .domain(self.domain)
            .case_type(self.secondary_case_type)
        ).run().hits[0]
        case_props = doc['case_properties']
        expected_geopoint_val = {
            'key': self.gps_prop_name,
            'value': '5.5 6.6',
            'geopoint_value': {
                'lat': 5.5,
                'lon': 6.6
            }
        }
        self.assertTrue(expected_geopoint_val in case_props)

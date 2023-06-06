from django.test import TestCase
from corehq.apps.geospatial.reports import _get_geo_location


class CaseManagementMapTestCase(TestCase):
    def setUp(self):
        pass

    def test_get_geo_location_returns_lat_lon(self):
        """_get_geo_location expects an es_case which is just a dictionary"""

        es_case = {'case_json': {'commcare_gps_point': '42.78 -91.82 0.0 0.0'}}
        self.assertEqual(_get_geo_location(es_case), {'lat': 42.78, 'lng': -91.82})

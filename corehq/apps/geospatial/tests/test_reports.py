import doctest

from nose.tools import assert_equal

from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.users.models import WebUser

from corehq.apps.geospatial.reports import (
    geojson_to_es_geoshape,
    CaseGroupingReport,
)


def test_geojson_to_es_geoshape():
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [125.6, 10.1]
        },
        "properties": {
            "name": "Dinagat Islands"
        }
    }
    es_geoshape = geojson_to_es_geoshape(geojson)
    assert_equal(es_geoshape, {
        "type": "point",  # NOTE: lowercase Elasticsearch type
        "coordinates": [125.6, 10.1]
    })


class TestCaseGroupingReport(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(username='test@cchq.com', domain=cls.domain)
        cls.user.save()
        cls.request_factory = RequestFactory()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        super().tearDownClass()

    def _create_dummy_request(self):
        request = self.request_factory.get('/some/url')
        request.couch_user = self.user
        request.domain = self.domain
        return request

    def test_case_row_order(self):
        request = self._create_dummy_request()
        report_obj = CaseGroupingReport(request, domain=self.domain)
        report_obj.rendered_as = 'view'
        context_data = report_obj.template_context
        expected_columns = ['case_id', 'gps_point', 'link']
        self.assertEqual(
            list(context_data['case_row_order'].keys()),
            expected_columns
        )


def test_doctests():
    import corehq.apps.geospatial.reports as reports

    results = doctest.testmod(reports)
    assert results.failed == 0

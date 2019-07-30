from __future__ import absolute_import, unicode_literals

import json
import uuid
from datetime import datetime

from django.conf import settings
from django.test import TestCase
from django.utils.http import urlencode

import six

from casexml.apps.case.mock import CaseBlock
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.api.models import ESXFormInstance
from corehq.apps.api.resources import v0_4
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.reportxform import transform_xform_for_report_forms_index
from corehq.pillows.xform import transform_xform_for_elasticsearch

from .utils import APIResourceTest, FakeXFormES


class TestXFormInstanceResource(APIResourceTest):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    resource = v0_4.XFormInstanceResource

    def _test_es_query(self, url_params, expected_query):

        fake_xform_es = FakeXFormES()

        prior_run_query = fake_xform_es.run_query

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        def mock_run_query(es_query):
            self.assertItemsEqual(es_query['filter']['and'], expected_query)
            return prior_run_query(es_query)

        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        response = self._assert_auth_get_resource('%s?%s' % (self.list_endpoint, urlencode(url_params)))
        self.assertEqual(response.status_code, 200)

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """
        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        # In order to test just the API code, we set up a fake XFormES (this should
        # really be a parameter to the XFormInstanceResource constructor)
        # and write the translated form directly; we are not trying to test
        # the ptop infrastructure.

        # the pillow is set to offline mode - elasticsearch not needed to validate
        fake_xform_es = FakeXFormES()
        v0_4.MOCK_XFORM_ES = fake_xform_es

        backend_form = XFormInstance(
            xmlns='fake-xmlns',
            domain=self.domain.name,
            received_on=datetime.utcnow(),
            edited_on=datetime.utcnow(),
            form={
                '#type': 'fake-type',
                '@xmlns': 'fake-xmlns',
                'meta': {'userID': 'metadata-user-id'},
            },
            auth_context={
                'user_id': 'auth-user-id',
                'domain': self.domain.name,
                'authenticated': True,
            },
        )
        backend_form.save()
        self.addCleanup(backend_form.delete)
        translated_doc = transform_xform_for_elasticsearch(backend_form.to_json())
        fake_xform_es.add_doc(translated_doc['_id'], translated_doc)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)

        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], backend_form.xmlns)
        self.assertEqual(api_form['received_on'], json_format_datetime(backend_form.received_on))
        self.assertEqual(api_form['metadata']['userID'], 'metadata-user-id')
        self.assertEqual(api_form['edited_by_user_id'], 'auth-user-id')

    def test_get_list_xmlns(self):
        expected = [
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'xmlns.exact': 'http://XMLNS'}}
        ]
        self._test_es_query({'xmlns': 'http://XMLNS'}, expected)

    def test_get_list_xmlns_exact(self):
        expected = [
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'xmlns.exact': 'http://XMLNS'}}
        ]
        self._test_es_query({'xmlns.exact': 'http://XMLNS'}, expected)

    def test_get_list_received_on(self):
        """
        Forms can be filtered by passing ?recieved_on_start=<date>&received_on_end=<date>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)
        expected = [
            {'range': {'received_on': {'gte': start_date.isoformat(), 'lte': end_date.isoformat()}}},
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'domain.exact': 'qwerty'}},
        ]
        params = {
            'received_on_end': end_date.isoformat(),
            'received_on_start': start_date.isoformat(),
        }
        self._test_es_query(params, expected)

    def test_get_list_ordering(self):
        '''
        Forms can be ordering ascending or descending on received_on; by default
        ascending.
        '''

        fake_xform_es = FakeXFormES()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        queries = []

        def mock_run_query(es_query):
            queries.append(es_query)
            return prior_run_query(es_query)

        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[0]['sort'], [{'received_on': {'missing': '_first', 'order': 'asc'}}])
        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=-received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[2]['sort'], [{'received_on': {'missing': '_last', 'order': 'desc'}}])

    def test_get_list_archived(self):
        expected = [
            {'or': [
                {'term': {'doc_type': 'xforminstance'}},
                {'term': {'doc_type': 'xformarchived'}}
            ]},
            {'term': {'domain.exact': 'qwerty'}},
        ]
        self._test_es_query({'include_archived': 'true'}, expected)

    @run_with_all_backends
    def test_fetching_xform_cases(self):
        fake_xform_es = FakeXFormES(ESXFormInstance)
        v0_4.MOCK_XFORM_ES = fake_xform_es

        # Create an xform that touches a case
        case_id = uuid.uuid4().hex
        form = submit_case_blocks(
            CaseBlock(
                case_id=case_id,
                create=True,
            ).as_text(),
            self.domain.name
        )[0]

        fake_xform_es.add_doc(form.form_id, transform_xform_for_elasticsearch(form.to_json()))

        # Fetch the xform through the API
        response = self._assert_auth_get_resource(self.single_endpoint(form.form_id) + "?cases__full=true")
        self.assertEqual(response.status_code, 200)
        cases = json.loads(response.content)['cases']

        # Confirm that the case appears in the resource
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['id'], case_id)


class TestReportPillow(TestCase):

    def test_xformPillowTransform(self):
        """
        Test to make sure report xform and reportxform pillows strip the appVersion dict to match the
        mappings
        """
        transform_functions = [transform_xform_for_report_forms_index, transform_xform_for_elasticsearch]
        bad_appVersion = {
            "_id": "foo",
            "domain": settings.ES_XFORM_FULL_INDEX_DOMAINS[0],
            'received_on': "2013-09-20T01:33:12Z",
            "form": {
                "meta": {
                    "@xmlns": "http://openrosa.org/jr/xforms",
                    "username": "someuser",
                    "instanceID": "foo",
                    "userID": "some_user_id",
                    "timeEnd": "2013-09-20T01:33:12Z",
                    "appVersion": {
                        "@xmlns": "http://commcarehq.org/xforms",
                        "#text": "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013"
                    },
                    "timeStart": "2013-09-19T01:13:20Z",
                    "deviceID": "somedevice"
                }
            }
        }
        for fn in transform_functions:
            cleaned = fn(bad_appVersion)
            self.assertFalse(isinstance(cleaned['form']['meta']['appVersion'], dict))
            self.assertTrue(isinstance(cleaned['form']['meta']['appVersion'], six.text_type))
            self.assertTrue(cleaned['form']['meta']['appVersion'], "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013")

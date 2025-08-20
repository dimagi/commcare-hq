import json

from django.test import TestCase

from corehq.apps.api.odata.views import (
    ODataCaseServiceView,
    ODataFormServiceView,
)

from .utils import CaseOdataTestMixin, FormOdataTestMixin


class TestCaseServiceDocument(TestCase, CaseOdataTestMixin):

    view_urlname = ODataCaseServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocument, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestCaseServiceDocument, cls).tearDownClass()

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        url = f'http://localhost:8000/a/test_domain/api/odata/cases/v1/{self.instance._id}/$metadata'
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': url,
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }],
        })


class TestFormServiceDocument(TestCase, FormOdataTestMixin):

    view_urlname = ODataFormServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestFormServiceDocument, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestFormServiceDocument, cls).tearDownClass()

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        url = f'http://localhost:8000/a/test_domain/api/odata/forms/v1/{self.instance._id}/$metadata'
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': url,
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }],
        })

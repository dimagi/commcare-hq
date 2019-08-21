from __future__ import absolute_import, unicode_literals

import json

from django.test import TestCase

from corehq.apps.api.odata.views import (
    ODataCaseServiceView,
    ODataFormServiceView,
)
from corehq.util.test_utils import flag_enabled

from .utils import CaseOdataTestMixin, FormOdataTestMixin


class TestCaseServiceDocument(TestCase, CaseOdataTestMixin):

    view_urlname = ODataCaseServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestCaseServiceDocument, cls).tearDownClass()

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/cases/my_config_id/$metadata',
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

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestFormServiceDocument, cls).tearDownClass()

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/forms/my_config_id/$metadata',
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }],
        })

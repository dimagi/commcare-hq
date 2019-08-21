from __future__ import absolute_import, unicode_literals

import json

from django.test import TestCase
from django.urls import reverse

from corehq.apps.api.odata.tests.utils import (
    OdataTestMixin,
    ensure_es_case_index_deleted,
    ensure_es_form_index_deleted,
    setup_es_case_index,
    setup_es_form_index,
)
from corehq.apps.api.resources.v0_5 import ODataCaseResource, ODataFormResource
from corehq.apps.export.models import (
    CaseExportInstance,
    FormExportInstance,
    TableConfiguration,
)
from corehq.util.test_utils import flag_enabled


class TestODataCaseFeed(TestCase, OdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestODataCaseFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()
        setup_es_case_index()

    @classmethod
    def tearDownClass(cls):
        ensure_es_case_index_deleted()
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestODataCaseFeed, cls).tearDownClass()

    def test_config_in_different_domain(self):
        export_config_in_other_domain = CaseExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[])],
            case_type='my_case_type',
            domain='different_domain'
        )
        export_config_in_other_domain.save()
        self.addCleanup(export_config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self.client.get(
                self._odata_feed_url_by_domain_and_config_id(self.domain.name, export_config_in_other_domain.get_id),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 404)

    def test_missing_config_id(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self.client.get(
                self._odata_feed_url_by_domain_and_config_id(self.domain.name, 'missing_config_id'),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 404)

    def test_request_succeeded(self):
        export_config = CaseExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[])],
            case_type='my_case_type',
            domain=self.domain.name,
        )
        export_config.save()
        self.addCleanup(export_config.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/cases/config_id/$metadata#feed',
                'value': []
            }
        )

    @property
    def view_url(self):
        return self._odata_feed_url_by_domain(self.domain.name)

    @staticmethod
    def _odata_feed_url_by_domain(domain_name):
        return TestODataCaseFeed._odata_feed_url_by_domain_and_config_id(domain_name, 'config_id')

    @staticmethod
    def _odata_feed_url_by_domain_and_config_id(domain_name, config_id):
        return reverse(
            'api_dispatch_detail',
            kwargs={
                'domain': domain_name,
                'api_name': 'v0.5',
                'resource_name': ODataCaseResource._meta.resource_name,
                'pk': config_id + '/feed',
            }
        )


class TestODataFormFeed(TestCase, OdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestODataFormFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()
        setup_es_form_index()

    @classmethod
    def tearDownClass(cls):
        ensure_es_form_index_deleted()
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestODataFormFeed, cls).tearDownClass()

    def test_config_in_different_domain(self):
        export_config_in_other_domain = FormExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[])],
            domain='different_domain'
        )
        export_config_in_other_domain.save()
        self.addCleanup(export_config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self.client.get(
                self._odata_feed_url_by_domain_and_config_id(
                    self.domain.name, export_config_in_other_domain.get_id),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 404)

    def test_missing_config_id(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self.client.get(
                self._odata_feed_url_by_domain_and_config_id(self.domain.name, 'missing_config_id'),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 404)

    def test_request_succeeded(self):
        export_config = FormExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[])],
            domain=self.domain.name,
            xmlns='my_xmlns',
        )
        export_config.save()
        self.addCleanup(export_config.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/forms/config_id/$metadata#feed',
                'value': []
            }
        )

    @property
    def view_url(self):
        return self._odata_feed_url_by_domain(self.domain.name)

    @staticmethod
    def _odata_feed_url_by_domain(domain_name):
        return TestODataFormFeed._odata_feed_url_by_domain_and_config_id(domain_name, 'config_id')

    @staticmethod
    def _odata_feed_url_by_domain_and_config_id(domain_name, config_id):
        return reverse(
            'api_dispatch_detail',
            kwargs={
                'domain': domain_name,
                'api_name': 'v0.5',
                'resource_name': ODataFormResource._meta.resource_name,
                'pk': config_id + '/feed',
            }
        )

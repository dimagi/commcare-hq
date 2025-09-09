import json

from django.test import TestCase
from django.urls import reverse

from corehq.apps.api.odata.tests.utils import (
    CaseOdataTestMixin,
    FormOdataTestMixin,
)
from corehq.apps.api.resources.v0_5 import ODataCaseResource, ODataFormResource
from corehq.apps.export.models import (
    CaseExportInstance,
    FormExportInstance,
    TableConfiguration,
)
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.util.test_utils import flag_enabled


@es_test(requires=[case_adapter, user_adapter], setup_class=True)
@flag_enabled('API_THROTTLE_WHITELIST')
class TestODataCaseFeed(TestCase, CaseOdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestODataCaseFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
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
        response = self.client.get(
            self._odata_feed_url_by_domain_and_config_id(self.domain.name, export_config_in_other_domain.get_id),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_config_id(self):
        correct_credentials = self._get_correct_credentials()
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
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(response['OData-Version'], '4.0')
        url = 'http://localhost:8000/a/test_domain/api/odata/cases/v1/config_id/$metadata#feed'
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                '@odata.context': url,
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
                'api_name': 'v1',
                'resource_name': ODataCaseResource._meta.resource_name,
                'pk': config_id + '/feed',
            }
        )


@es_test(requires=[form_adapter, user_adapter], setup_class=True)
@flag_enabled('API_THROTTLE_WHITELIST')
class TestODataFormFeed(TestCase, FormOdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestODataFormFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
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
        response = self.client.get(
            self._odata_feed_url_by_domain_and_config_id(
                self.domain.name, export_config_in_other_domain.get_id),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_config_id(self):
        correct_credentials = self._get_correct_credentials()
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
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(response['OData-Version'], '4.0')
        url = 'http://localhost:8000/a/test_domain/api/odata/forms/v1/config_id/$metadata#feed'
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                '@odata.context': url,
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
                'api_name': 'v1',
                'resource_name': ODataFormResource._meta.resource_name,
                'pk': config_id + '/feed',
            }
        )

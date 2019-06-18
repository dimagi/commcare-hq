from __future__ import absolute_import
from __future__ import unicode_literals

import json
from mock import patch

from django.test import TestCase
from django.urls import reverse

from elasticsearch.exceptions import ConnectionError

from casexml.apps.case.mock import CaseFactory
from corehq.apps.api.odata.tests.utils import (
    OdataTestMixin,
    generate_api_key_from_web_user,
)
from corehq.apps.api.resources.v0_5 import ODataCommCareCaseResource, ODataXFormInstanceResource
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.case import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import flag_enabled, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping


class TestCaseOdataFeed(TestCase, OdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestCaseOdataFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestCaseOdataFeed, cls).tearDownClass()

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 404)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 404)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            self._odata_feed_url_by_domain(other_domain.name),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_request_succeeded(self):
        self._test_request_succeeded()

    @flag_enabled('ODATA')
    def _test_request_succeeded(self):
        with trap_extra_setup(ConnectionError):
            elasticsearch_instance = get_es_new()
            initialize_index_and_mapping(elasticsearch_instance, CASE_INDEX_INFO)
        self.addCleanup(self._ensure_case_index_deleted)

        case = CaseFactory('test_domain').create_case(case_type='my_case_type', update={'abc': 'xyz'})
        send_to_elasticsearch('cases', transform_case_for_elasticsearch(case.to_json()))

        self.web_user.set_role(self.domain.name, 'admin')
        self.web_user.save()

        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.serializers.get_case_type_to_properties', return_value={
            'my_case_type': ['abc']
        }):
            response = self._execute_query(correct_credentials)

        self.assertEqual(response.status_code, 200)
        feed = json.loads(response.content.decode('utf-8'))
        self.assertCountEqual(['@odata.context', 'value'], feed)
        self.assertEqual(
            feed['@odata.context'],
            'http://localhost:8000/a/test_domain/api/v0.5/odata/Cases/$metadata#my_case_type'
        )
        feed_value = feed['value']
        self.assertEqual(len(feed_value), 1)
        feed_value_row = feed_value[0]
        self.assertCountEqual(
            feed_value_row,
            [
                'case_id', 'closed', 'date_closed', 'date_modified', 'domain', 'opened_by', 'properties',
                'server_date_modified' ,'server_date_opened', 'user_id', 'xform_ids'
            ]
        )
        self.assertCountEqual(
            ['abc', 'backendid', 'casename', 'casetype', 'dateopened', 'ownerid'],
            feed_value_row['properties']
        )
        self.assertEqual(type(feed_value_row['xform_ids']), list)

    @property
    def view_url(self):
        return self._odata_feed_url_by_domain(self.domain.name)

    @staticmethod
    def _odata_feed_url_by_domain(domain_name):
        return reverse(
            'api_dispatch_detail',
            kwargs={
                'domain': domain_name,
                'api_name': 'v0.5',
                'resource_name': ODataCommCareCaseResource._meta.resource_name,
                'pk': 'my_case_type',
            }
        )

    @staticmethod
    def _ensure_case_index_deleted():
        ensure_index_deleted(CASE_INDEX_INFO.index)


class TestCaseOdataFeedUsingApiKey(TestCaseOdataFeed):

    @classmethod
    def setUpClass(cls):
        super(TestCaseOdataFeedUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestCaseOdataFeedUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestCaseOdataFeedWithTwoFactorUsingApiKey(TestCaseOdataFeedUsingApiKey):
    pass


class TestFormOdataFeed(TestCase, OdataTestMixin):

    @classmethod
    def setUpClass(cls):
        super(TestFormOdataFeed, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestFormOdataFeed, cls).tearDownClass()

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 404)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 404)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            self._odata_feed_url_by_domain(other_domain.name),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_request_succeeded(self):
        self._test_request_succeeded()

    @flag_enabled('ODATA')
    def _test_request_succeeded(self):
        with trap_extra_setup(ConnectionError):
            elasticsearch_instance = get_es_new()
            initialize_index_and_mapping(elasticsearch_instance, XFORM_INDEX_INFO)
        self.addCleanup(self._ensure_xform_index_deleted)

        self.web_user.set_role(self.domain.name, 'admin')
        self.web_user.save()

        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/Forms/my_app_id/$metadata#my_xmlns',
                'value': []
            }
        )

    @property
    def view_url(self):
        return self._odata_feed_url_by_domain(self.domain.name)

    @staticmethod
    def _odata_feed_url_by_domain(domain_name):
        return reverse(
            'api_dispatch_detail',
            kwargs={
                'domain': domain_name,
                'api_name': 'v0.5',
                'resource_name': ODataXFormInstanceResource._meta.resource_name,
                'pk': 'my_app_id/my_xmlns',
            }
        )

    @staticmethod
    def _ensure_xform_index_deleted():
        ensure_index_deleted(XFORM_INDEX_INFO.index)


class TestFormOdataFeedUsingApiKey(TestFormOdataFeed):

    @classmethod
    def setUpClass(cls):
        super(TestFormOdataFeedUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestFormOdataFeedUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestFormOdataFeedWithTwoFactorUsingApiKey(TestFormOdataFeedUsingApiKey):
    pass

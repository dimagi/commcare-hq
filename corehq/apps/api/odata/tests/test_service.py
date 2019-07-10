from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.test import TestCase
from django.urls import reverse

from mock import patch

from corehq.apps.api.odata.tests.utils import (
    CaseOdataTestMixin,
    DeprecatedCaseOdataTestMixin,
    DeprecatedFormOdataTestMixin,
    FormOdataTestMixin,
    generate_api_key_from_web_user,
)
from corehq.apps.api.odata.views import (
    ODataCaseServiceView,
    DeprecatedODataCaseServiceView,
    DeprecatedODataFormServiceView,
    ODataFormServiceView,
)
from corehq.apps.domain.models import Domain
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.util.test_utils import flag_enabled


class TestDeprecatedCaseServiceDocument(TestCase, DeprecatedCaseOdataTestMixin):

    view_urlname = DeprecatedODataCaseServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedCaseServiceDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestDeprecatedCaseServiceDocument, cls).tearDownClass()

    def test_no_credentials(self):
        with flag_enabled('ODATA'):
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        with flag_enabled('ODATA'):
            response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self.client.get(
                reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch('corehq.apps.api.odata.views.get_case_types_for_domain_es', return_value=set()):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {"@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Cases/$metadata", "value": []}
        )

    def test_with_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch(
                'corehq.apps.api.odata.views.get_case_types_for_domain_es',
                return_value=['case_type_1', 'case_type_2'],  # return ordered iterable for deterministic test
            ):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                "@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Cases/$metadata",
                "value": [
                    {'kind': 'EntitySet', 'name': 'case_type_1', 'url': 'case_type_1'},
                    {'kind': 'EntitySet', 'name': 'case_type_2', 'url': 'case_type_2'},
                ],
            }
        )


class TestDeprecatedCaseServiceDocumentUsingApiKey(TestDeprecatedCaseServiceDocument):

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedCaseServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestDeprecatedCaseServiceDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestDeprecatedCaseServiceDocumentWithTwoFactorUsingApiKey(TestDeprecatedCaseServiceDocumentUsingApiKey):
    pass


class TestDeprecatedFormServiceDocument(TestCase, DeprecatedFormOdataTestMixin):

    view_urlname = DeprecatedODataFormServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedFormServiceDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestDeprecatedFormServiceDocument, cls).tearDownClass()

    def test_no_credentials(self):
        with flag_enabled('ODATA'):
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        with flag_enabled('ODATA'):
            response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self.client.get(
                reverse(self.view_urlname, kwargs={'domain': other_domain.name, 'app_id': 'my_app_id'}),
                HTTP_AUTHORIZATION='Basic ' + correct_credentials,
            )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_no_xmlnss(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch('corehq.apps.api.odata.views.get_xmlns_by_app', return_value=[]):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                "@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Forms/my_app_id/$metadata",
                "value": [],
            }
        )

    def test_with_xmlnss(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            with patch('corehq.apps.api.odata.views.get_xmlns_by_app', return_value=['xmlns_1', 'xmlns_2']):
                response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {
                "@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Forms/my_app_id/$metadata",
                "value": [
                    {'kind': 'EntitySet', 'name': 'xmlns_1', 'url': 'xmlns_1'},
                    {'kind': 'EntitySet', 'name': 'xmlns_2', 'url': 'xmlns_2'},
                ],
            }
        )


class TestDeprecatedFormServiceDocumentUsingApiKey(TestDeprecatedFormServiceDocument):

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedFormServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestDeprecatedFormServiceDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestDeprecatedFormServiceDocumentWithTwoFactorUsingApiKey(TestDeprecatedFormServiceDocumentUsingApiKey):
    pass


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

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/cases/$metadata',
            'value': [],
        })

    def test_populated_service_document(self):
        odata_config_1 = CaseExportInstance(domain=self.domain.name, is_odata_config=True)
        odata_config_1.save()
        self.addCleanup(odata_config_1.delete)

        odata_config_2 = CaseExportInstance(domain=self.domain.name, is_odata_config=True)
        odata_config_2.save()
        self.addCleanup(odata_config_2.delete)

        non_odata_config = CaseExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = CaseExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        response_content = json.loads(response.content.decode('utf-8'))
        self.assertCountEqual(response_content, ['@odata.context', 'value'])
        self.assertEqual(
            response_content['@odata.context'],
            'http://localhost:8000/a/test_domain/api/v0.5/odata/cases/$metadata'
        )
        self.assertCountEqual(response_content['value'], [
            {
                'url': odata_config_1.get_id,
                'kind': 'EntitySet',
                'name': odata_config_1.get_id,
            },
            {
                'url': odata_config_2.get_id,
                'kind': 'EntitySet',
                'name': odata_config_2.get_id,
            },
        ])


class TestCaseServiceDocumentUsingApiKey(TestCaseServiceDocument):

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestDeprecatedFormServiceDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestCaseServiceDocumentWithTwoFactorUsingApiKey(TestCaseServiceDocumentUsingApiKey):
    pass


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

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_permissions(self):
        self.web_user.set_role(self.domain.name, 'none')
        self.web_user.save()
        self.addCleanup(self._setup_user_permissions)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_successful_request(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertEqual(json.loads(response.content.decode('utf-8')), {
            '@odata.context': 'http://localhost:8000/a/test_domain/api/v0.5/odata/forms/$metadata',
            'value': [],
        })

    def test_populated_service_document(self):
        odata_config_1 = FormExportInstance(domain=self.domain.name, is_odata_config=True)
        odata_config_1.save()
        self.addCleanup(odata_config_1.delete)

        odata_config_2 = FormExportInstance(domain=self.domain.name, is_odata_config=True)
        odata_config_2.save()
        self.addCleanup(odata_config_2.delete)

        non_odata_config = FormExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = FormExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('ODATA'):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['OData-Version'], '4.0')
        response_content = json.loads(response.content.decode('utf-8'))
        self.assertCountEqual(response_content, ['@odata.context', 'value'])
        self.assertEqual(
            response_content['@odata.context'],
            'http://localhost:8000/a/test_domain/api/v0.5/odata/forms/$metadata'
        )
        self.assertCountEqual(response_content['value'], [
            {
                'url': odata_config_1.get_id,
                'kind': 'EntitySet',
                'name': odata_config_1.get_id,
            },
            {
                'url': odata_config_2.get_id,
                'kind': 'EntitySet',
                'name': odata_config_2.get_id,
            },
        ])


class TestFormServiceDocumentUsingApiKey(TestFormServiceDocument):

    @classmethod
    def setUpClass(cls):
        super(TestFormServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return cls._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestFormServiceDocumentWithTwoFactorUsingApiKey(TestFormServiceDocumentUsingApiKey):
    pass

from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.test import TestCase
from django.urls import reverse

from mock import patch

from corehq.apps.api.odata.tests.utils import (
    CaseOdataTestMixin,
    FormOdataTestMixin,
    generate_api_key_from_web_user,
)
from corehq.apps.api.odata.views import ODataCaseServiceView, ODataFormServiceView
from corehq.apps.domain.models import Domain
from corehq.util.test_utils import flag_enabled


class TestCaseServiceDocumentCase(TestCase, CaseOdataTestMixin):

    view_urlname = ODataCaseServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocumentCase, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestCaseServiceDocumentCase, cls).tearDownClass()

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


class TestCaseServiceDocumentUsingApiKey(TestCaseServiceDocumentCase):

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestCaseServiceDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


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


class TestFormServiceDocumentUsingApiKey(TestFormServiceDocument):

    @classmethod
    def setUpClass(cls):
        super(TestFormServiceDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = generate_api_key_from_web_user(cls.web_user)

    @classmethod
    def _get_correct_credentials(cls):
        return TestFormServiceDocumentUsingApiKey._get_basic_credentials(cls.web_user.username, cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestFormServiceDocumentWithTwoFactorUsingApiKey(TestFormServiceDocumentUsingApiKey):
    pass

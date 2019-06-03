from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.test import Client, TestCase
from django.urls import reverse

from mock import patch
from tastypie.models import ApiKey

from corehq.apps.api.odata.tests.utils import CaseOdataTestMixin, FormOdataTestMixin
from corehq.apps.api.odata.views import ODataCaseServiceView, ODataFormServiceView
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestCaseServiceDocumentCase(TestCase, CaseOdataTestMixin):

    view_urlname = ODataCaseServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseServiceDocumentCase, cls).setUpClass()
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(TestCaseServiceDocumentCase, cls).tearDownClass()

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

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('ODATA')
    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_case_types_for_domain_es', return_value=set()):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {"@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Cases/$metadata", "value": []}
        )

    @flag_enabled('ODATA')
    def test_with_case_types(self):
        correct_credentials = self._get_correct_credentials()
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
        cls.api_key = ApiKey.objects.get_or_create(user=cls.web_user.get_django_user())[0]
        cls.api_key.key = cls.api_key.generate_key()
        cls.api_key.save()

    @classmethod
    def _get_correct_credentials(cls):
        return TestCaseServiceDocumentUsingApiKey._get_basic_credentials('test_user', cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestCaseServiceDocumentWithTwoFactorUsingApiKey(TestCaseServiceDocumentUsingApiKey):

    # Duplicated because flag on inherited method doesn't work when outer flag is used
    @flag_enabled('ODATA')
    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_case_types_for_domain_es', return_value=set()):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {"@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Cases/$metadata", "value": []}
        )

    # Duplicated because flag on inherited method doesn't work when outer flag is used
    @flag_enabled('ODATA')
    def test_with_case_types(self):
        correct_credentials = self._get_correct_credentials()
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


class TestFormServiceDocument(TestCase, FormOdataTestMixin):

    view_urlname = ODataFormServiceView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestFormServiceDocument, cls).setUpClass()
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
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
            reverse(self.view_urlname, kwargs={'domain': other_domain.name, 'app_id': 'my_app_id'}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('ODATA')
    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_xmlns_by_app', return_value=[]):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {"@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Forms/my_app_id/$metadata", "value": []}
        )

    @flag_enabled('ODATA')
    def test_with_case_types(self):
        correct_credentials = self._get_correct_credentials()
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
        cls.api_key = ApiKey.objects.get_or_create(user=cls.web_user.get_django_user())[0]
        cls.api_key.key = cls.api_key.generate_key()
        cls.api_key.save()

    @classmethod
    def _get_correct_credentials(cls):
        return TestFormServiceDocumentUsingApiKey._get_basic_credentials('test_user', cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestFormServiceDocumentWithTwoFactorUsingApiKey(TestFormServiceDocumentUsingApiKey):

    # Duplicated because flag on inherited method doesn't work when outer flag is used
    @flag_enabled('ODATA')
    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_xmlns_by_app', return_value=[]):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content.decode('utf-8')),
            {"@odata.context": "http://localhost:8000/a/test_domain/api/v0.5/odata/Forms/my_app_id/$metadata", "value": []}
        )

    # Duplicated because flag on inherited method doesn't work when outer flag is used
    @flag_enabled('ODATA')
    def test_with_case_types(self):
        correct_credentials = self._get_correct_credentials()
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

from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from django.test import Client, TestCase
from django.urls import reverse

from mock import patch
from tastypie.models import ApiKey

from corehq.apps.api.odata.tests.utils import OdataTestMixin
from corehq.apps.api.odata.views import ODataCaseMetadataView
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestMetadataDocument(TestCase, OdataTestMixin, TestXmlMixin):

    view_urlname = ODataCaseMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestMetadataDocument, cls).setUpClass()
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(TestMetadataDocument, cls).tearDownClass()

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
        with patch('corehq.apps.api.odata.views.get_case_type_to_properties', return_value={}):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    @flag_enabled('ODATA')
    def test_populated_metadata_document(self):
        correct_credentials = self._get_correct_credentials()
        with patch(
            'corehq.apps.api.odata.views.get_case_type_to_properties',
            return_value=OrderedDict([
                ('case_type_with_no_case_properties', []),
                ('case_type_with_case_properties', ['property_1', 'property_2']),
            ])
        ):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('populated_metadata_document', override_path=PATH_TO_TEST_DATA)
        )


class TestMetadataDocumentUsingApiKey(TestMetadataDocument):

    @classmethod
    def setUpClass(cls):
        super(TestMetadataDocumentUsingApiKey, cls).setUpClass()
        cls.api_key = ApiKey.objects.get_or_create(user=cls.web_user.get_django_user())[0]
        cls.api_key.key = cls.api_key.generate_key()
        cls.api_key.save()

    @classmethod
    def _get_correct_credentials(cls):
        return TestMetadataDocumentUsingApiKey._get_basic_credentials('test_user', cls.api_key.key)


@flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
class TestMetadataDocumentWithTwoFactorUsingApiKey(TestMetadataDocumentUsingApiKey):

    # Duplicated because flag on inherited method doesn't work when outer flag is used
    @flag_enabled('ODATA')
    def test_no_case_types(self):
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_case_type_to_properties', return_value={}):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    @flag_enabled('ODATA')
    def test_populated_metadata_document(self):
        correct_credentials = self._get_correct_credentials()
        with patch(
            'corehq.apps.api.odata.views.get_case_type_to_properties',
            return_value=OrderedDict([
                ('case_type_with_no_case_properties', []),
                ('case_type_with_case_properties', ['property_1', 'property_2']),
            ])
        ):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('populated_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

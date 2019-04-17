from __future__ import absolute_import
from __future__ import unicode_literals

import base64

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from mock import patch

from corehq import toggles
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestMetadataDocument(TestCase, TestXmlMixin):

    @classmethod
    def setUpClass(cls):
        super(TestMetadataDocument, cls).setUpClass()
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')
        cls.metadata_url = reverse('odata_meta', kwargs={'domain': cls.domain.name})

    def tearDown(self):
        toggles.ODATA.set(self.domain.name, False, toggles.NAMESPACE_DOMAIN)
        super(TestMetadataDocument, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(TestMetadataDocument, cls).tearDownClass()

    def test_no_credentials(self):
        response = self.client.get(self.metadata_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_metadata_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_metadata_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_no_case_types(self):
        self._enable_odata_toggle_for_domain()
        correct_credentials = self._get_correct_credentials()
        with patch('corehq.apps.api.odata.views.get_case_type_to_properties', return_value={}):
            response = self._execute_metadata_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('empty_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    def test_populated_metadata_document(self):
        self._enable_odata_toggle_for_domain()
        correct_credentials = self._get_correct_credentials()
        with patch(
            'corehq.apps.api.odata.views.get_case_type_to_properties',
            return_value={
                'case_type_with_no_case_properties': [],
                'case_type_with_case_properties': ['property_1', 'property_2'],
            }
        ):
            response = self._execute_metadata_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertXmlEqual(
            response.content,
            self.get_xml('populated_metadata_document', override_path=PATH_TO_TEST_DATA)
        )

    def _enable_odata_toggle_for_domain(self):
        toggles.ODATA.set(self.domain.name, True, toggles.NAMESPACE_DOMAIN)

    def _execute_metadata_query(self, credentials):
        return self.client.get(self.metadata_url, HTTP_AUTHORIZATION='Basic ' + credentials)

    @staticmethod
    def _get_correct_credentials():
        return TestMetadataDocument._get_basic_credentials('test_user', 'my_password')

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode("{}:{}".format(username, password).encode('utf-8')).decode('utf-8')

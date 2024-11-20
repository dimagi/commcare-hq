from django.test import TestCase
from django.urls import reverse

from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataFormMetadataView,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.export.models import (
    CaseExportInstance,
)

from .utils import CaseOdataTestMixin, FormOdataTestMixin

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestCaseMetadataDocument(TestCase, CaseOdataTestMixin, TestXmlMixin):

    view_urlname = ODataCaseMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseMetadataDocument, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestCaseMetadataDocument, cls).tearDownClass()

    def test_missing_feed(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(
            correct_credentials,
            reverse(
                self.view_urlname,
                kwargs={
                    'domain': self.domain.name,
                    'api_version': 'v1',
                    'config_id': 'FAKEID',
                }
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_populated_metadata_document(self):
        non_odata_config = CaseExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = CaseExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml(
                'populated_case_odata_metadata_document_from_config',
                override_path=PATH_TO_TEST_DATA
            ),
            response.content
        )


class TestFormMetadataDocument(TestCase, FormOdataTestMixin, TestXmlMixin):

    view_urlname = ODataFormMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestFormMetadataDocument, cls).setUpClass()
        cls._set_up_class()
        cls._setup_accounting()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        cls._teardown_accounting()
        super(TestFormMetadataDocument, cls).tearDownClass()

    def test_missing_feed(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(
            correct_credentials,
            reverse(
                self.view_urlname,
                kwargs={
                    'domain': self.domain.name,
                    'api_version': 'v1',
                    'config_id': 'FAKEID',
                }
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_populated_metadata_document(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response['OData-Version'], '4.0')
        self.assertXmlEqual(
            self.get_xml(
                'populated_form_odata_metadata_document_from_config',
                override_path=PATH_TO_TEST_DATA
            ),
            response.content
        )

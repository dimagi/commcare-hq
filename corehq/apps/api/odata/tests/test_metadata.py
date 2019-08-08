from __future__ import absolute_import, unicode_literals

from django.test import TestCase

from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataFormMetadataView,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    FormExportInstance,
    PathNode,
    TableConfiguration,
)
from corehq.util.test_utils import flag_enabled

from .utils import CaseOdataTestMixin, FormOdataTestMixin

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestCaseMetadataDocument(TestCase, CaseOdataTestMixin, TestXmlMixin):

    view_urlname = ODataCaseMetadataView.urlname

    @classmethod
    def setUpClass(cls):
        super(TestCaseMetadataDocument, cls).setUpClass()
        cls._set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestCaseMetadataDocument, cls).tearDownClass()

    def test_missing_feed(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_populated_metadata_document(self):
        odata_config = CaseExportInstance(
            _id='my_config_id',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(label='closed', selected=True,
                                     # this is what exports generate for a base level property
                                     item=ExportItem(path=[PathNode(name='closed')])),
                        ExportColumn(label='date_modified', selected=True,
                                     item=ExportItem(path=[PathNode(name='date_modified')])),
                        ExportColumn(label='selected_property_1', selected=True),
                        ExportColumn(label='selected_property_2', selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )
        odata_config.save()
        self.addCleanup(odata_config.delete)

        non_odata_config = CaseExportInstance(domain=self.domain.name)
        non_odata_config.save()
        self.addCleanup(non_odata_config.delete)

        config_in_other_domain = CaseExportInstance(domain='other_domain', is_odata_config=True)
        config_in_other_domain.save()
        self.addCleanup(config_in_other_domain.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
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

    @classmethod
    def tearDownClass(cls):
        cls._teardownclass()
        super(TestFormMetadataDocument, cls).tearDownClass()

    def test_missing_feed(self):
        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
            response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    def test_populated_metadata_document(self):
        odata_config = FormExportInstance(
            _id='my_config_id',
            domain=self.domain.name,
            is_odata_config=True,
            tables=[
                TableConfiguration(
                    columns=[
                        ExportColumn(label='received_on', selected=True,
                                     item=ExportItem(path=[PathNode(name='received_on')])),
                        ExportColumn(label='started_time', selected=True,
                                     item=ExportItem(path=[
                                         PathNode(name='form'),
                                         PathNode(name='meta'),
                                         PathNode(name='timeStart'),
                                     ])),

                        ExportColumn(label='selected_property_1', selected=True),
                        ExportColumn(label='selected_property_2', selected=True),
                        ExportColumn(label='unselected_property'),
                    ],
                ),
            ]
        )
        odata_config.save()
        self.addCleanup(odata_config.delete)

        correct_credentials = self._get_correct_credentials()
        with flag_enabled('BI_INTEGRATION_PREVIEW', is_preview=True):
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

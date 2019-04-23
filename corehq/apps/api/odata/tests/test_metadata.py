from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from django.test import TestCase

from mock import patch

from corehq.apps.api.odata.tests.utils import OdataTestMixin
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.util.test_utils import flag_enabled

PATH_TO_TEST_DATA = ('..', '..', 'api', 'odata', 'tests', 'data')


class TestMetadataDocument(OdataTestMixin, TestCase, TestXmlMixin):

    view_urlname = 'odata_meta'

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

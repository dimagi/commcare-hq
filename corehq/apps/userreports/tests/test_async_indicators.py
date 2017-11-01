from __future__ import absolute_import
from django.test import SimpleTestCase

from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.tests.utils import get_data_source_with_related_doc_type


class RunAsynchronousTest(SimpleTestCase):
    def _create_data_source_config(self, indicators=None):
        default_indicator = [{
            "type": "expression",
            "column_id": "laugh_sound",
            "datatype": "string",
            "expression": {
                'type': 'named',
                'name': 'laugh_sound'
            }
        }]

        return DataSourceConfiguration.wrap({
            'display_name': 'Mother Indicators',
            'doc_type': 'DataSourceConfiguration',
            'domain': 'test',
            'referenced_doc_type': 'CommCareCase',
            'table_id': 'mother_indicators',
            'configured_filter': {},
            'configured_indicators': indicators or default_indicator
        })

    def test_async_not_configured(self):
        indicator_configuration = self._create_data_source_config()
        adapter = get_indicator_adapter(indicator_configuration)
        self.assertFalse(adapter.run_asynchronous)

    def test_async_configured(self):
        indicator_configuration = self._create_data_source_config()
        indicator_configuration.asynchronous = True
        adapter = get_indicator_adapter(indicator_configuration)
        self.assertTrue(adapter.run_asynchronous)

    # def test_related_doc_expression(self):
    #     indicator_configuration = self._create_data_source_config([{
    #         "datatype": "string",
    #         "type": "expression",
    #         "column_id": "confirmed_referral_target",
    #         "expression": {
    #             "type": "related_doc",
    #             "related_doc_type": "CommCareUser",
    #             "doc_id_expression": {
    #                 "type": "property_path",
    #                 "property_path": ["form", "meta", "userID"]
    #             },
    #             "value_expression": {
    #                 "type": "property_path",
    #                 "property_path": [
    #                     "user_data",
    #                     "confirmed_referral_target"
    #                 ]
    #             }
    #         }
    #     }])
    #
    #     adapter = get_indicator_adapter(indicator_configuration)
    #     self.assertTrue(adapter.run_asynchronous)
    #
    # def test_named_expression(self):
    #     indicator_configuration = get_data_source_with_related_doc_type()
    #     adapter = get_indicator_adapter(indicator_configuration)
    #     self.assertTrue(adapter.run_asynchronous)

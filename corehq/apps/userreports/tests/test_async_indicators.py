from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase, TestCase

from corehq.apps.userreports.models import DataSourceConfiguration, AsyncIndicator
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.tests.utils import get_data_source_with_related_doc_type

import six

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


class TestBulkUpdate(TestCase):
    def tearDown(self):
        AsyncIndicator.objects.all().delete()

    def _get_indicator_data(self):
        return {
            i.doc_id: i.indicator_config_ids
            for i in AsyncIndicator.objects.all()
        }

    def test_update_record(self):
        domain = 'test-update-record'
        doc_type = 'form'
        initial_data = {
            'd1': ['c1', 'c2'],
            'd2': ['c1'],
            'd3': ['c2']
        }
        AsyncIndicator.objects.bulk_create([
            AsyncIndicator(doc_id=doc_id, doc_type=doc_type, domain=domain, indicator_config_ids=sorted(config_ids))
            for doc_id, config_ids in six.iteritems(initial_data)
        ])
        updated_data = {
            'd2': ['c2'],
            'd3': ['c3'],
            'd4': ['c2', 'c1'],
            'd5': ['c4']
        }

        with self.assertNumQueries(3):
            # 3 queries, 1 for query, 1 for update, 1 for create
            AsyncIndicator.bulk_update_records(updated_data, domain, doc_type)

        self.assertEqual(
            self._get_indicator_data(),
            {
                'd1': ['c1', 'c2'],
                'd2': ['c2'],
                'd3': ['c3'],
                'd4': ['c1', 'c2'],
                'd5': ['c4']
            }
        )

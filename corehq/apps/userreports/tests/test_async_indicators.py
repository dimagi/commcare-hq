from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.models import DataSourceConfiguration, AsyncIndicator
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.apps.userreports.tests.utils import get_data_source_with_related_doc_type, load_data_from_db


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


class BulkAsyncIndicatorProcessingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        domain_name = "bulk_async_indicator_processing"
        cls.domain = Domain.get_or_create_with_name(domain_name, is_active=True)

        def _make_config(indicators):
            return DataSourceConfiguration(
                domain=domain_name,
                display_name='foo',
                referenced_doc_type='CommCareCase',
                table_id=clean_table_name(domain_name, str(uuid.uuid4().hex)),
                configured_indicators=indicators
            )

        cls.config1 = _make_config(
            [{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'name'
                },
                "column_id": 'name',
                "display_name": 'name',
                "datatype": "string"
            }]
        )
        cls.config1.save()
        cls.config2 = _make_config(
            [{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'color'
                },
                "column_id": 'color',
                "display_name": 'color',
                "datatype": "string"
            }]
        )
        cls.config2.save()

        for config in [cls.config1, cls.config2]:
            get_indicator_adapter(config, raise_errors=True).build_table()


    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        docs = [
            {
                "_id": str(i),
                "domain": "domain",
                "doc_type": "CommCareCase",
                "name": 'doc_name_' + str(i),
                "color": 'doc_color_' + str(i)
            }
            for i in range(10)
        ]

        AsyncIndicator.bulk_creation(
            [doc["_id"] for doc in docs],
            "CommCareCase",
            self.domain,
            []
        )

    def tearDown(self):
        AsyncIndicator.objects.all().delete()

    def _assert_rows_in_ucr(self, config, rows):
        results = load_data_from_db(get_table_name(self.domain.name, config.table_id))
        self.assertEqual(rows, list(results))

    def test_basic_run(self):
        # multiple indicators, multiple config, many-to-many
        self._assert_rows_in_ucr(self.config1, [])

    def test_non_similar_indicators(self):
        # some indicators to first config, other to the second config
        pass

    def test_unknown_config(self):
        # multiple indicators, one invalid config, one valid
        pass

    def test_failure(self):
        # multiple indicators, exception in bulk-save for one config
        pass


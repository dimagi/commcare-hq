from django.test import TestCase
from unittest.mock import patch

from corehq.apps.userreports.sql.adapter import IndicatorSqlAdapter
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.app_manager.helpers import clean_table_name


class TestIndicatorSqlAdapter(TestCase):

    @staticmethod
    def _create_data_source_config(domain):
        indicator = {
            "type": "expression",
            "expression": {
                "type": "property_name",
                "property_name": 'name'
            },
            "column_id": 'name',
            "display_name": 'name',
            "datatype": "string"
        }
        return DataSourceConfiguration(
            domain=domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=clean_table_name('domain', 'test-table'),
            configured_indicators=[indicator],
        )

    @patch("corehq.apps.userreports.sql.adapter.register_data_source_row_change")
    def test_bulk_delete_table_dont_exist(self, register_data_source_row_change_mock):
        config = self._create_data_source_config("test-domain")
        adapter = IndicatorSqlAdapter(config)

        docs = [{'_id': '1'}]
        self.assertFalse(adapter.table_exists)

        adapter.bulk_delete(docs)
        register_data_source_row_change_mock.assert_not_called()

    @patch("corehq.apps.userreports.sql.adapter.register_data_source_row_change")
    def test_bulk_delete_table_exists(self, register_data_source_row_change_mock):
        config = self._create_data_source_config("test-domain2")
        adapter = IndicatorSqlAdapter(config)

        docs = [{'_id': '1'}]
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        self.assertTrue(adapter.table_exists)

        adapter.bulk_delete(docs)
        register_data_source_row_change_mock.assert_called()

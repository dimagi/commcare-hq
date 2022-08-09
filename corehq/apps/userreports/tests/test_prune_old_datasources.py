from django.test import TestCase

from django.core.management import call_command

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.elastic import get_es_new
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted, reset_es_index


@es_test
class TestPruneOldDatasources(TestCase):

    def test_non_orphaned_tables_are_not_dropped(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        self.addCleanup(config.delete)
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)

        call_command('prune_old_datasources', engine_id='ucr')

        self.assertTrue(adapter.table_exists)

    def test_orphaned_table_of_active_domain_is_not_dropped(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        config.delete()

        call_command('prune_old_datasources', engine_id='ucr')

        self.assertTrue(adapter.table_exists)

    def test_orphaned_table_of_active_domain_is_dropped_with_force_delete(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        config.delete()

        call_command('prune_old_datasources', engine_id='ucr', force_delete=True)

        self.assertFalse(adapter.table_exists)

    def test_orphaned_table_of_deleted_domain_is_dropped(self):
        config = self._create_data_source_config(self.deleted_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        config.delete()

        call_command('prune_old_datasources', engine_id='ucr')

        self.assertFalse(adapter.table_exists)

    def test_no_changes_if_dry_run_enabled(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        config.delete()

        call_command('prune_old_datasources', engine_id='ucr', dry_run=True)

        self.assertTrue(adapter.table_exists)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('test')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)

    def setUp(self):
        super().setUp()
        self._setup_es()

    @staticmethod
    def _create_data_source_config(domain_name):
        return DataSourceConfiguration(
            domain=domain_name,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=clean_table_name(domain_name, 'test-table'),
            configured_indicators=[{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'name'
                },
                "column_id": 'name',
                "display_name": 'name',
                "datatype": "string"
            }],
        )

    def _setup_es(self):
        self.es = get_es_new()
        reset_es_index(DOMAIN_INDEX_INFO)
        initialize_index_and_mapping(self.es, DOMAIN_INDEX_INFO)
        self.addCleanup(ensure_index_deleted, DOMAIN_INDEX_INFO.index)

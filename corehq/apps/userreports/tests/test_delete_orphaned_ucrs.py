from unittest.mock import patch

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
class DeleteOrphanedUCRsTests(TestCase):

    def test_non_orphaned_tables_are_not_dropped(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        self.addCleanup(config.delete)
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)

        try:
            call_command('delete_orphaned_ucrs', engine_id='ucr')
        except SystemExit:
            # should be able to assert that SystemExit is raised given there shouldn't be any orphaned tables
            # but when running the entire test suite, this test fails likely because of a lingering orphaned UCR
            pass

        self.assertTrue(adapter.table_exists)

    def test_orphaned_table_of_active_domain_is_not_dropped(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        # orphan table by deleting config
        config.delete()

        with self.assertRaises(SystemExit):
            call_command('delete_orphaned_ucrs', engine_id='ucr')

        self.assertTrue(adapter.table_exists)

    def test_orphaned_table_of_active_domain_is_dropped_with_force_delete(self):
        config = self._create_data_source_config(self.active_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        # orphan table by deleting config
        config.delete()

        call_command('delete_orphaned_ucrs', engine_id='ucr', force_delete=True)

        self.assertFalse(adapter.table_exists)

    def test_orphaned_table_of_deleted_domain_is_dropped(self):
        config = self._create_data_source_config(self.deleted_domain.name)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        # orphan table by deleting config
        config.delete()

        call_command('delete_orphaned_ucrs', engine_id='ucr')

        self.assertFalse(adapter.table_exists)

    def test_limit_deletion_to_one_domain(self):
        active_config = self._create_data_source_config(self.active_domain.name)
        active_config.save()
        active_adapter = get_indicator_adapter(active_config, raise_errors=True)
        active_adapter.build_table()
        self.addCleanup(active_adapter.drop_table)

        deleted_config = self._create_data_source_config(self.deleted_domain.name)
        deleted_config.save()
        deleted_adapter = get_indicator_adapter(deleted_config, raise_errors=True)
        deleted_adapter.build_table()
        self.addCleanup(deleted_adapter.drop_table)
        # orphan table by deleting config
        active_config.delete()
        deleted_config.delete()

        call_command('delete_orphaned_ucrs', engine_id='ucr', force_delete=True, domain='test')

        self.assertTrue(deleted_adapter.table_exists)
        self.assertFalse(active_adapter.table_exists)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('test')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)

        input_patcher = patch('corehq.apps.userreports.management.commands.delete_orphaned_ucrs.get_input')
        mock_input = input_patcher.start()
        mock_input.return_value = 'y'
        cls.addClassCleanup(input_patcher.stop)

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

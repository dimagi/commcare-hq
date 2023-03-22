from unittest.mock import ANY, patch

from django.core.management import call_command
from django.test import TestCase


from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.domains import domain_adapter

from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.dbaccessors import (
    drop_orphaned_ucrs,
    get_orphaned_ucrs,
)
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter


@es_test(requires=[domain_adapter])
class BaseOrphanedUCRTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('test')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)

        input_patcher = patch('corehq.apps.userreports.management.commands.manage_orphaned_ucrs.input')
        mock_input = input_patcher.start()
        mock_input.return_value = 'y'
        cls.addClassCleanup(input_patcher.stop)

    def create_ucr(self, domain, tablename, is_orphan=False):
        config = self._create_data_source_config(domain.name, tablename)
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        if is_orphan:
            config.delete()
        else:
            self.addCleanup(config.delete)
        return adapter.get_table().name

    @staticmethod
    def _create_data_source_config(domain_name, tablename='test-table'):
        return DataSourceConfiguration(
            domain=domain_name,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=clean_table_name(domain_name, tablename),
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


@es_test
class GetOrphanedUCRsTests(BaseOrphanedUCRTest):

    def test_returns_empty_if_no_orphaned_tables(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=False)
        self.assertEqual(get_orphaned_ucrs('ucr'), [])

    def test_returns_deleted_domain_ucrs_when_ignore_active_domains_is_true(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=True)
        deleted_domain_ucr = self.create_ucr(self.deleted_domain,
                                             'deleted-table', is_orphan=True)

        # ignore_active_domains is True by default
        orphaned_ucrs = get_orphaned_ucrs('ucr')

        self.assertEqual(orphaned_ucrs, [deleted_domain_ucr])

    def test_includes_active_domain_ucrs_when_ignore_active_domains_is_false(self):
        active_domain_ucr = self.create_ucr(self.active_domain,
                                            'active-table', is_orphan=True)
        deleted_domain_ucr = self.create_ucr(self.deleted_domain,
                                             'deleted-table', is_orphan=True)

        orphaned_ucrs = get_orphaned_ucrs('ucr', ignore_active_domains=False)

        self.assertEqual(sorted(orphaned_ucrs),
                         sorted([active_domain_ucr, deleted_domain_ucr]))

    def test_returns_for_specific_domain_when_domain_is_specified(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=True)
        deleted_domain_ucr = self.create_ucr(self.deleted_domain,
                                             'deleted-table', is_orphan=True)

        orphaned_ucrs = get_orphaned_ucrs('ucr', ignore_active_domains=False,
                                          domain=self.deleted_domain.name)

        self.assertEqual(orphaned_ucrs, [deleted_domain_ucr])

    def test_raises_exception_if_domain_is_active_but_ignore_active_domains_is_true(self):
        with self.assertRaises(AssertionError):
            get_orphaned_ucrs('ucr', ignore_active_domains=True,
                              domain=self.active_domain.name)

    def test_raises_exception_if_database_does_not_exist(self):
        with self.assertRaises(ValueError):
            get_orphaned_ucrs('database')


@es_test
class DropUCRTablesTests(BaseOrphanedUCRTest):

    def test_ucrs_are_dropped(self):
        # want access to the adapter, so don't use create_ucr helper
        config = self._create_data_source_config(self.active_domain.name,
                                                 'orphaned-table')
        config.save()
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)
        config.delete()

        drop_orphaned_ucrs('ucr', [adapter.get_table().name])

        self.assertFalse(adapter.table_exists)


@es_test
class ManageOrphanedUCRsTests(BaseOrphanedUCRTest):

    def setUp(self):
        super().setUp()
        drop_ucrs_patcher = patch(
            'corehq.apps.userreports.management.commands.manage_orphaned_ucrs'
            '.drop_orphaned_ucrs')
        self.mock_drop_ucrs = drop_ucrs_patcher.start()
        self.addClassCleanup(drop_ucrs_patcher.stop)

    def test_non_orphaned_tables_are_not_dropped(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=False)
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr')
        self.mock_drop_ucrs.assert_not_called()

    def test_orphaned_table_for_active_domain_is_not_dropped_if_ignore_active_domains_is_true(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=True)
        # ignore_active_domains is true by default
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr')
        self.mock_drop_ucrs.assert_not_called()

    def test_orphaned_table_for_active_domain_is_dropped_if_ignore_active_domains_is_false(self):
        self.create_ucr(self.active_domain, 'active-table', is_orphan=True)
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr',
                     ignore_active_domains=False)
        self.mock_drop_ucrs.assert_called()

    def test_orphaned_table_for_deleted_domain_is_dropped_if_ignore_active_domains_is_true(self):
        self.create_ucr(self.deleted_domain, 'deleted-table', is_orphan=True)
        # ignore_active_domains is true by default
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr')
        self.mock_drop_ucrs.assert_called()

    def test_orphaned_table_for_deleted_domain_is_dropped_if_ignore_active_domains_is_false(self):
        self.create_ucr(self.deleted_domain, 'deleted-table', is_orphan=True)
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr',
                     ignore_active_domains=False)
        self.mock_drop_ucrs.assert_called()

    def test_orphaned_table_for_deleted_domain_is_dropped_if_domain_is_set(self):
        orphaned_ucr = self.create_ucr(self.deleted_domain, 'deleted-table',
                                       is_orphan=True)
        call_command('manage_orphaned_ucrs', 'delete', engine_id='ucr',
                     domain=self.deleted_domain.name)
        self.mock_drop_ucrs.assert_called_with(ANY, [orphaned_ucr])

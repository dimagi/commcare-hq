from django.test import TestCase
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.fixtures.models import (
    LookupTable,
    LookupTableRow,
    TypeField,
    Field,
)
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.updates import update_fixture


class TestUpdateFixturesReal(TestCase):
    def test_update_creates_new_synced_fixture(self):
        self._create_table(self.upstream_domain, 'test-table', ['col_1'], [{'col_1': 'one'}, {'col_1': 'two'}])

        update_fixture(self.link, 'test-table')

        created_table = LookupTable.objects.by_domain_tag(self.downstream_domain, 'test-table')
        self.assertEqual(created_table.tag, 'test-table')
        self.assertTrue(created_table.is_synced)
        self.assertColumnsEqual(created_table, ['col_1'])
        self.assertTableFieldsEqual(created_table, [{'col_1': 'one'}, {'col_1': 'two'}])

    def test_syncs_existing_fixture(self):
        upstream_cols = ['col_1']
        downstream_cols = ['col_2']
        upstream_rows = [{'col_1': 'one'}]
        downstream_rows = [{'col_2': 'two'}]
        self._create_table(self.upstream_domain, 'test-table', upstream_cols, upstream_rows)
        self._create_table(self.downstream_domain, 'test-table', downstream_cols, downstream_rows, is_synced=True)

        update_fixture(self.link, 'test-table')

        created_table = LookupTable.objects.by_domain_tag(self.downstream_domain, 'test-table')
        self.assertColumnsEqual(created_table, upstream_cols)
        self.assertTableFieldsEqual(created_table, upstream_rows)

    def test_update_raises_error_on_unsynced_duplicate_name(self):
        self._create_table(self.upstream_domain, 'test-table', ['col_1'], [])
        self._create_table(self.downstream_domain, 'test-table', ['col_2'], [], is_synced=False)

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push Lookup Table "test-table" due to matching (same Table ID) unlinked Lookup Table'
                ' in the downstream project space. Please edit the Lookup Table to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link them.'):
            update_fixture(self.link, 'test-table')

    def test_produces_pull_message(self):
        self._create_table(self.upstream_domain, 'test-table', ['col_1'], [])
        self._create_table(self.downstream_domain, 'test-table', ['col_2'], [], is_synced=False)

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to sync Lookup Table "test-table" due to matching (same Table ID) unlinked Lookup Table'
                ' in the downstream project space. Please edit the Lookup Table to resolve the matching or click'
                ' "Sync & Overwrite" to overwrite and link them.'):
            update_fixture(self.link, 'test-table', is_pull=True)

    def test_force_update_overwrites_conflicting_duplicate_name(self):
        upstream_cols = ['col_1']
        downstream_cols = ['col_2']
        upstream_rows = [{'col_1': 'one'}]
        downstream_rows = [{'col_2': 'two'}]
        self._create_table(self.upstream_domain, 'test-table', upstream_cols, upstream_rows)
        self._create_table(self.downstream_domain, 'test-table', downstream_cols, downstream_rows)

        update_fixture(self.link, 'test-table', overwrite=True)

        created_table = LookupTable.objects.by_domain_tag(self.downstream_domain, 'test-table')
        self.assertColumnsEqual(created_table, upstream_cols)
        self.assertTableFieldsEqual(created_table, upstream_rows)

    def test_syncing_local_table_raises_error(self):
        self._create_table(self.upstream_domain, 'test-table', ['col_1'], [], is_global=False)

        with self.assertRaisesMessage(UnsupportedActionError, "Found non-global lookup table 'test-table'"):
            update_fixture(self.link, 'test-table')

    def setUp(self):
        self.downstream_domain = 'downstream'
        self.upstream_domain = 'upstream'
        self.link = DomainLink(linked_domain=self.downstream_domain, master_domain=self.upstream_domain)

    def _create_table(self, domain, tag, col_names, rows, is_global=True, is_synced=False):
        columns = [TypeField(name=col_name) for col_name in col_names]
        table = LookupTable.objects.create(
            domain=domain, tag=tag, fields=columns, is_global=is_global, is_synced=is_synced)

        for i, row in enumerate(rows):
            fields = {key: [Field(value=val)] for (key, val) in row.items()}
            LookupTableRow.objects.create(domain=domain, table_id=table.id, fields=fields, sort_key=i)

        return table

    def assertColumnsEqual(self, table, expected_column_names):
        cols = [col.name for col in table.fields]
        self.assertEqual(cols, expected_column_names)

    def assertTableFieldsEqual(self, table, expected_field_values):
        rows = LookupTableRow.objects.filter(domain=table.domain, table_id=table.id)
        field_values = [row.fields_without_attributes for row in rows]
        self.assertListEqual(field_values, expected_field_values)

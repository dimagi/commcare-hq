from django.test import TestCase
from corehq.apps.fixtures.models import LookupTable, TypeField, LookupTableRow, Field
from corehq.apps.linked_domain.exceptions import UnsupportedActionError

from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.updates import update_fixture


def items_to_rows(items):
    if not items:
        return []

    # This makes the assumption that all items share the same keys, which are defined in the first item
    header = [header_name for header_name in list(items[0].fields.keys())]
    rows = [[val[0].value for val in list(item.fields.values())] for item in items]
    return (header, rows)


class FixtureUpdateTests(TestCase):
    def setUp(self):
        self.upstream_domain = 'upstream-domain'
        self.downstream_domain = 'downstream-domain'
        self.link = DomainLink(linked_domain=self.downstream_domain, master_domain=self.upstream_domain)
        super().setUp()

    def test_new_fixture_is_sent_to_downstream_domain(self):
        self._create_table(self.upstream_domain, 'test-fixture',
            ['col_one', 'col_two'],
            [['val1', 'val2'], ['val3', 'val4']])

        update_fixture(self.link, 'test-fixture')

        created_fixture = LookupTable.objects.by_domain_tag(self.downstream_domain, 'test-fixture')
        fixture_items = list(LookupTableRow.objects.iter_rows(self.downstream_domain, table_id=created_fixture.id))
        (headers, rows) = items_to_rows(fixture_items)

        self.assertEqual(created_fixture.tag, 'test-fixture')
        self.assertTrue(created_fixture.is_global)
        self.assertEqual(headers, ['col_one', 'col_two'])
        self.assertEqual(rows, [['val1', 'val2'], ['val3', 'val4']])

    def test_existing_fixture_is_not_overwritten(self):
        self._create_table(self.upstream_domain, 'test-fixture', ['new_header'], [['new_value']])
        self._create_table(self.downstream_domain, 'test-fixture', ['old_header'], [['old_value']])

        with self.assertRaises(UnsupportedActionError) as cm:
            update_fixture(self.link, 'test-fixture')

        self.assertEqual(str(cm.exception), 'Failed to push Lookup Table "test-fixture" due to matching '
                         '(same Table ID) unlinked Lookup Table in the downstream project space.'
                         ' Please edit the Lookup Table to resolve the matching or click "Push & Overwrite"'
                         ' to overwrite and link them.')

    def test_previously_synced_fixtures_are_overwritten(self):
        self._create_table(self.upstream_domain, 'test-fixture', ['new_header'], [['new_value']])
        self._create_table(self.downstream_domain, 'test-fixture', ['old_header'], [['old_value']], is_synced=True)

        update_fixture(self.link, 'test-fixture')
        updated_fixture = LookupTable.objects.by_domain_tag(self.downstream_domain, 'test-fixture')
        fixture_items = list(LookupTableRow.objects.iter_rows(self.downstream_domain, table_id=updated_fixture.id))
        (headers, rows) = items_to_rows(fixture_items)

        self.assertEqual(headers, ['new_header'])
        self.assertEqual(rows, [['new_value']])

    def test_local_data_types_cannot_be_synced(self):
        self._create_table(self.upstream_domain, 'test-fixture', ['header'], [['value']], is_global=False)

        with self.assertRaises(UnsupportedActionError) as cm:
            update_fixture(self.link, 'test-fixture')

        self.assertEqual(str(cm.exception), "Found non-global lookup table 'test-fixture'.")

    def _create_table(self, domain, tag, columns, rows, is_global=True, is_synced=False):
        fields = [TypeField(name=name) for name in columns]
        table = LookupTable(domain=domain, tag=tag, is_global=is_global, fields=fields)
        if is_synced:
            table.is_synced = True
        table.save()

        for (index, row) in enumerate(rows):
            pairs = zip(columns, row)
            fields = {name: [Field(value=val)] for (name, val) in pairs}
            item = LookupTableRow(domain=domain, table=table, fields=fields, sort_key=index)
            item.save()

        return table

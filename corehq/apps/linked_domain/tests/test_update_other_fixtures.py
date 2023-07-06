from django.test import TestCase
from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_types,
    get_fixture_data_type_by_tag,
    get_fixture_items_for_data_type,
    delete_fixture_items_for_data_type
)
from corehq.apps.fixtures.models import (
    FixtureDataType, FixtureTypeField, FixtureDataItem, FieldList, FixtureItemField
)
from corehq.apps.linked_domain.exceptions import UnsupportedActionError

from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.updates import update_fixture


def delete_all_domain_fixtures(domain):
    for fixture in get_fixture_data_types(domain):
        delete_fixture(fixture)


def delete_fixture(fixture):
    delete_fixture_items_for_data_type(fixture.domain, fixture._id)
    fixture.delete()


def items_to_rows(items):
    if not items:
        return []

    # This makes the assumption that all items share the same keys, which are defined in the first item
    header = [header_name for header_name in items[0].fields.keys()]
    rows = [[val.field_list[0].field_value for val in item.fields.values()] for item in items]
    return (header, rows)


class FixtureUpdateTests(TestCase):
    def setUp(self):
        self.upstream_domain = 'upstream-domain'
        self.downstream_domain = 'downstream-domain'
        self.link = DomainLink(linked_domain=self.downstream_domain, master_domain=self.upstream_domain)
        super().setUp()

    def tearDown(self):
        delete_all_domain_fixtures(self.upstream_domain)
        delete_all_domain_fixtures(self.downstream_domain)

    def test_new_fixture_is_sent_to_downstream_domain(self):
        self._create_table(self.upstream_domain, 'test-fixture',
            ['col_one', 'col_two'],
            [['val1', 'val2'], ['val3', 'val4']])

        update_fixture(self.link, 'test-fixture')

        created_fixture = get_fixture_data_type_by_tag(self.downstream_domain, 'test-fixture')
        fixture_items = get_fixture_items_for_data_type(self.downstream_domain, created_fixture._id)
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

        self.assertEqual(str(cm.exception), "Existing lookup table found for 'test-fixture'. "
            "Please remove this table before trying to sync again")

    def test_previously_synced_fixtures_are_overwritten(self):
        self._create_table(self.upstream_domain, 'test-fixture', ['new_header'], [['new_value']])
        self._create_table(self.downstream_domain, 'test-fixture', ['old_header'], [['old_value']], is_synced=True)

        update_fixture(self.link, 'test-fixture')
        updated_fixture = get_fixture_data_type_by_tag(self.downstream_domain, 'test-fixture')
        fixture_items = get_fixture_items_for_data_type(self.downstream_domain, updated_fixture._id)
        (headers, rows) = items_to_rows(fixture_items)

        self.assertEqual(headers, ['new_header'])
        self.assertEqual(rows, [['new_value']])

    def test_local_data_types_cannot_be_synced(self):
        self._create_table(self.upstream_domain, 'test-fixture', ['header'], [['value']], is_global=False)

        with self.assertRaises(UnsupportedActionError) as cm:
            update_fixture(self.link, 'test-fixture')

        self.assertEqual(str(cm.exception), "Found non-global lookup table 'test-fixture'.")

    def _create_table(self, domain, tag, columns, rows, is_global=True, is_synced=False):
        fields = [FixtureTypeField(field_name=name) for name in columns]
        table = FixtureDataType(domain=domain, tag=tag, is_global=is_global, fields=fields)
        if is_synced:
            table.is_synced = True
        table.save()

        for row in rows:
            pairs = zip(columns, row)
            fields = {name: FieldList(field_list=[FixtureItemField(field_value=val)]) for (name, val) in pairs}
            item = FixtureDataItem(domain=domain, data_type_id=table._id, fields=fields)
            item.save()

        return table

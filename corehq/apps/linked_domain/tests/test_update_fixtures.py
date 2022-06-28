from unittest.mock import patch

from corehq.apps.fixtures.dbaccessors import (
    delete_all_fixture_data,
    delete_fixture_items_for_data_type,
    get_fixture_data_types,
    get_fixture_items_for_data_type,
)
from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    FixtureItemField,
    FixtureTypeField,
    LookupTable,
    LookupTableRow,
)
from corehq.apps.fixtures.upload.run_upload import clear_fixture_quickcache
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_fixture


class TestUpdateFixtures(BaseLinkedDomainTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.table = FixtureDataType(
            domain=cls.domain,
            tag='moons',
            is_global=True,
            fields=[
                FixtureTypeField(field_name="name"),
                FixtureTypeField(field_name="planet"),
            ],
        )
        cls.table.save()
        cls.addClassCleanup(delete_all_fixture_data)

    def setUp(self):
        # Reset table content for each test
        for item in [
            FixtureDataItem(
                domain=self.domain,
                data_type_id=self.table._id,
                fields={
                    'name': FieldList(field_list=[FixtureItemField(field_value='Io')]),
                    'planet': FieldList(field_list=[FixtureItemField(field_value='Jupiter')]),
                },
            ),
            FixtureDataItem(
                domain=self.domain,
                data_type_id=self.table._id,
                fields={
                    'name': FieldList(field_list=[FixtureItemField(field_value='Europa')]),
                    'planet': FieldList(field_list=[FixtureItemField(field_value='Jupiter')]),
                },
            ),
            FixtureDataItem(
                domain=self.domain,
                data_type_id=self.table._id,
                fields={
                    'name': FieldList(field_list=[FixtureItemField(field_value='Callisto')]),
                    'planet': FieldList(field_list=[FixtureItemField(field_value='Jupiter')]),
                },
            ),
        ]:
            item.save()

    def tearDown(self):
        delete_fixture_items_for_data_type(self.domain, self.table._id)
        linked_types = get_fixture_data_types(self.linked_domain, bypass_cache=True)
        for data_type in linked_types:
            delete_fixture_items_for_data_type(self.linked_domain, data_type._id)
        FixtureDataType.bulk_delete(linked_types)
        clear_fixture_quickcache(self.domain, [self.table])
        clear_fixture_quickcache(self.linked_domain, linked_types)

    def test_update_fixture(self):
        self.assertEqual([], get_fixture_data_types(self.linked_domain))

        # Update linked domain
        update_fixture(self.domain_link, self.table.tag)

        # Linked domain should now have master domain's table and rows
        linked_types = get_fixture_data_types(self.linked_domain)
        self.assertEqual({'moons'}, {t.tag for t in linked_types})
        self.assertEqual({self.linked_domain}, {t.domain for t in linked_types})
        items = get_fixture_items_for_data_type(self.linked_domain, linked_types[0]._id)
        self.assertEqual({self.linked_domain}, {i.domain for i in items})
        self.assertEqual({linked_types[0]._id}, {i.data_type_id for i in items})
        self.assertEqual([
            'Callisto', 'Europa', 'Io', 'Jupiter', 'Jupiter', 'Jupiter',
        ], sorted([
            i.fields[field_name].field_list[0].field_value for i in items for field_name in i.fields.keys()
        ]))

        # Master domain's table and rows should be untouched
        master_types = get_fixture_data_types(self.domain)
        self.assertEqual({'moons'}, {t.tag for t in master_types})
        self.assertEqual({self.domain}, {t.domain for t in master_types})
        master_items = get_fixture_items_for_data_type(self.domain, master_types[0]._id)
        self.assertEqual([
            'Callisto', 'Europa', 'Io', 'Jupiter', 'Jupiter', 'Jupiter',
        ], sorted([
            i.fields[field_name].field_list[0].field_value
            for i in master_items
            for field_name in i.fields.keys()
        ]))

        # Update rows in master table and re-update linked domain
        master_items[-1].delete()       # Callisto
        FixtureDataItem(
            domain=self.domain,
            data_type_id=self.table._id,
            fields={
                'name': FieldList(field_list=[FixtureItemField(field_value='Thalassa')]),
                'planet': FieldList(field_list=[FixtureItemField(field_value='Neptune')]),
            },
        ).save()
        FixtureDataItem(
            domain=self.domain,
            data_type_id=self.table._id,
            fields={
                'name': FieldList(field_list=[FixtureItemField(field_value='Naiad')]),
                'planet': FieldList(field_list=[FixtureItemField(field_value='Neptune')]),
            },
        ).save()
        clear_fixture_quickcache(self.domain, get_fixture_data_types(self.domain))
        clear_fixture_cache(self.domain)
        update_fixture(self.domain_link, self.table.tag)

        # Linked domain should still have one table, with the new rows
        linked_types = get_fixture_data_types(self.linked_domain)
        self.assertEqual(1, len(linked_types))
        self.assertEqual('moons', linked_types[0].tag)
        items = get_fixture_items_for_data_type(self.linked_domain, linked_types[0]._id)
        self.assertEqual(4, len(items))
        self.assertEqual([
            'Europa', 'Io', 'Jupiter', 'Jupiter', 'Naiad', 'Neptune', 'Neptune', 'Thalassa',
        ], sorted([
            i.fields[field_name].field_list[0].field_value for i in items for field_name in i.fields.keys()
        ]))
        # Linked SQL rows should have been deleted
        rows = LookupTableRow.objects.filter(table_id=linked_types[0]._id)
        self.assertEqual(
            ['Europa', 'Io', 'Jupiter', 'Jupiter', 'Naiad', 'Neptune', 'Neptune', 'Thalassa'],
            sorted(field[0].value for i in rows for field in i.fields.values()),
        )

    def test_update_fixture_with_stale_caches(self):
        def stale_caches():
            from dimagi.utils.couch.bulk import CouchTransaction
            table = LookupTable.objects.by_domain_tag(self.domain, "moons")
            # populate row cache
            rows = get_fixture_items_for_data_type(self.domain, table._migration_couch_id)
            assert len(rows) == 3, rows
            with CouchTransaction() as tx:
                for row in rows:
                    tx.delete(row)

        self.assertEqual([], get_fixture_data_types(self.linked_domain, bypass_cache=True))

        stale_caches()

        # Update linked domain
        update_fixture(self.domain_link, "moons")

        # Linked domain should now have master domain's table and rows
        table, = get_fixture_data_types(self.linked_domain, bypass_cache=True)
        self.assertFalse(get_fixture_items_for_data_type(self.linked_domain, table._id))

    def test_update_fixture_stale_cache_race(self):
        from .. import updates as mod

        def delete_and_stale_cache(*args):
            real_delete_fixture_items_for_data_type(*args)
            # populate items cache before new items are created (race condition)
            items = get_fixture_items_for_data_type(*args)
            assert not items, items

        real_delete_fixture_items_for_data_type = mod.delete_fixture_items_for_data_type
        with patch.object(mod, "delete_fixture_items_for_data_type", delete_and_stale_cache):
            update_fixture(self.domain_link, "moons")

        # stale items cache should have been reset by now
        table, = get_fixture_data_types(self.linked_domain)
        items = get_fixture_items_for_data_type(self.linked_domain, table._id)
        self.assertEqual(
            ['Callisto', 'Europa', 'Io', 'Jupiter', 'Jupiter', 'Jupiter'],
            sorted(i.fields[field_name].field_list[0].field_value for i in items for field_name in i.fields),
        )

    def test_update_global_only(self):
        other_table = FixtureDataType(
            domain=self.domain,
            tag='jellyfish',
            is_global=False,
            fields=[
                FixtureTypeField(field_name="genus"),
                FixtureTypeField(field_name="species"),
            ],
        )
        other_table.save()
        clear_fixture_quickcache(self.domain, get_fixture_data_types(self.domain))
        clear_fixture_cache(self.domain)

        with self.assertRaises(UnsupportedActionError):
            update_fixture(self.domain_link, 'jellyfish')

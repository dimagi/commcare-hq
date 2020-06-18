from corehq.apps.fixtures.dbaccessors import (
    delete_all_fixture_data_types,
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
)
from corehq.apps.fixtures.upload.run_upload import clear_fixture_quickcache
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_fixtures


class TestUpdateFixtures(BaseLinkedAppsTest):
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

    @classmethod
    def tearDownClass(cls):
        for data_type in get_fixture_data_types(cls.domain):
            delete_fixture_items_for_data_type(cls.domain, data_type._id)
        for data_type in get_fixture_data_types(cls.linked_domain):
            delete_fixture_items_for_data_type(cls.linked_domain, data_type._id)
        delete_all_fixture_data_types()
        super().tearDownClass()

    def test_update_fixtures(self):
        self.assertEqual([], get_fixture_data_types(self.linked_domain))

        # Update linked domain
        update_fixtures(self.domain_link)

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
        update_fixtures(self.domain_link)

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
        FixtureDataItem(
            domain=self.domain,
            data_type_id=self.table._id,
            fields={
                'name': FieldList(field_list=[FixtureItemField(field_value='Ganymede')]),
                'planet': FieldList(field_list=[FixtureItemField(field_value='Jupiter')]),
            },
        ).save()
        clear_fixture_quickcache(self.domain, get_fixture_data_types(self.domain))
        clear_fixture_cache(self.domain)

        with self.assertRaises(UnsupportedActionError):
            update_fixtures(self.domain_link)

        # Despite the exception, the global table should have gotten updated
        linked_types = get_fixture_data_types(self.linked_domain)
        self.assertEqual({'moons'}, {t.tag for t in linked_types})
        items = get_fixture_items_for_data_type(self.linked_domain, linked_types[0]._id)
        self.assertEqual(4, len(items))
        self.assertEqual([
            'Callisto', 'Europa', 'Ganymede', 'Io', 'Jupiter', 'Jupiter', 'Jupiter', 'Jupiter',
        ], sorted([
            i.fields[field_name].field_list[0].field_value for i in items for field_name in i.fields.keys()
        ]))

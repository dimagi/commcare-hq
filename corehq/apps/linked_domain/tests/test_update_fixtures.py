from corehq.apps.fixtures.models import (
    LookupTable,
    LookupTableRow,
    TypeField,
    Field,
)
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_fixture


class TestUpdateFixtures(BaseLinkedDomainTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.table = LookupTable(
            domain=cls.domain,
            tag='moons',
            is_global=True,
            fields=[
                TypeField(name="name"),
                TypeField(name="planet"),
            ],
        )
        cls.table.save()

    def setUp(self):
        # Reset table content for each test
        for item in [
            LookupTableRow(
                domain=self.domain,
                table_id=self.table.id,
                fields={
                    'name': [Field(value='Io')],
                    'planet': [Field(value='Jupiter')],
                },
                sort_key=0,
            ),
            LookupTableRow(
                domain=self.domain,
                table_id=self.table.id,
                fields={
                    'name': [Field(value='Europa')],
                    'planet': [Field(value='Jupiter')],
                },
                sort_key=1,
            ),
            LookupTableRow(
                domain=self.domain,
                table_id=self.table.id,
                fields={
                    'name': [Field(value='Callisto')],
                    'planet': [Field(value='Jupiter')],
                },
                sort_key=2,
            ),
        ]:
            item.save()

    def test_update_fixture(self):
        self.assertFalse(LookupTable.objects.by_domain(self.linked_domain).count())

        # Update linked domain
        update_fixture(self.domain_link, self.table.tag)

        # Linked domain should now have master domain's table and rows
        linked_types = LookupTable.objects.by_domain(self.linked_domain)
        self.assertEqual({'moons'}, {t.tag for t in linked_types})
        self.assertEqual({self.linked_domain}, {t.domain for t in linked_types})
        items = list(LookupTableRow.objects.iter_rows(self.linked_domain, table_id=linked_types[0].id))
        self.assertEqual({self.linked_domain}, {i.domain for i in items})
        self.assertEqual({linked_types[0].id}, {i.table_id for i in items})
        self.assertEqual([
            'Callisto', 'Europa', 'Io', 'Jupiter', 'Jupiter', 'Jupiter',
        ], sorted([
            i.fields[field_name][0].value for i in items for field_name in i.fields.keys()
        ]))

        # Master domain's table and rows should be untouched
        master_types = LookupTable.objects.by_domain(self.domain)
        self.assertEqual({'moons'}, {t.tag for t in master_types})
        self.assertEqual({self.domain}, {t.domain for t in master_types})
        master_items = list(LookupTableRow.objects.iter_rows(self.domain, table_id=master_types[0].id))
        self.assertEqual([
            'Callisto', 'Europa', 'Io', 'Jupiter', 'Jupiter', 'Jupiter',
        ], sorted([
            i.fields[field_name][0].value
            for i in master_items
            for field_name in i.fields.keys()
        ]))

        # Update rows in master table and re-update linked domain
        master_items[-1].delete()       # Callisto
        LookupTableRow(
            domain=self.domain,
            table_id=self.table.id,
            fields={
                'name': [Field(value='Thalassa')],
                'planet': [Field(value='Neptune')],
            },
            sort_key=0,
        ).save()
        LookupTableRow(
            domain=self.domain,
            table_id=self.table.id,
            fields={
                'name': [Field(value='Naiad')],
                'planet': [Field(value='Neptune')],
            },
            sort_key=1,
        ).save()
        clear_fixture_cache(self.domain)
        update_fixture(self.domain_link, self.table.tag)

        # Linked domain should still have one table, with the new rows
        linked_types = LookupTable.objects.by_domain(self.linked_domain)
        self.assertEqual(1, len(linked_types))
        self.assertEqual('moons', linked_types[0].tag)
        items = list(LookupTableRow.objects.iter_rows(self.linked_domain, table_id=linked_types[0].id))
        self.assertEqual(4, len(items))
        self.assertEqual([
            'Europa', 'Io', 'Jupiter', 'Jupiter', 'Naiad', 'Neptune', 'Neptune', 'Thalassa',
        ], sorted([
            i.fields[field_name][0].value for i in items for field_name in i.fields.keys()
        ]))
        # Linked SQL rows should have been deleted
        rows = LookupTableRow.objects.filter(table_id=linked_types[0].id)
        self.assertEqual(
            ['Europa', 'Io', 'Jupiter', 'Jupiter', 'Naiad', 'Neptune', 'Neptune', 'Thalassa'],
            sorted(field[0].value for i in rows for field in i.fields.values()),
        )

    def test_update_global_only(self):
        other_table = LookupTable(
            domain=self.domain,
            tag='jellyfish',
            is_global=False,
            fields=[
                TypeField(name="genus"),
                TypeField(name="species"),
            ],
        )
        other_table.save()
        clear_fixture_cache(self.domain)

        with self.assertRaises(UnsupportedActionError):
            update_fixture(self.domain_link, 'jellyfish')

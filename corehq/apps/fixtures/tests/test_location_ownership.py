from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.models import CommCareUser


class TestLocationOwnership(LocationHierarchyTestCase):

    domain = 'fixture-location-ownership-testing'
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        super(TestLocationOwnership, cls).setUpClass()
        cls.tag = "big-mac-index"

        data_type = LookupTable(
            domain=cls.domain,
            tag=cls.tag,
            description="Big Mac Index",
            fields=[
                TypeField(name="cost"),
                TypeField(name="region"),
            ],
            item_attributes=[],
        )
        data_type.save()

        def make_data_item(location_name, cost):
            """Make a fixture data item and assign it to location_name"""
            data_item = LookupTableRow(
                domain=cls.domain,
                table_id=data_type.id,
                fields={
                    "cost": [Field(value=cost)],
                    "location_name": [Field(value=location_name)],
                },
                item_attributes={},
                sort_key=0
            )
            data_item.save()

            LookupTableRowOwner(
                domain=cls.domain,
                owner_id=cls.locations[location_name].location_id,
                owner_type=OwnerType.Location,
                row_id=data_item.id,
            ).save()

        make_data_item('Suffolk', '8')
        make_data_item('Boston', '10')
        make_data_item('Somerville', '7')

        cls.no_location_user = CommCareUser.create(cls.domain, 'no_location', '***', None, None)
        cls.suffolk_user = CommCareUser.create(cls.domain, 'guy-from-suffolk', '***', None, None)
        cls.suffolk_user.set_location(cls.locations['Suffolk'])
        cls.boston_user = CommCareUser.create(cls.domain, 'guy-from-boston', '***', None, None)
        cls.boston_user.set_location(cls.locations['Boston'])
        cls.middlesex_user = CommCareUser.create(cls.domain, 'guy-from-middlesex', '***', None, None)
        cls.middlesex_user.set_location(cls.locations['Middlesex'])

    @staticmethod
    def _get_value(fixture_item, field_name):
        return fixture_item.fields[field_name][0].value

    def test_sees_fixture_at_own_location(self):
        fixture_items = list(LookupTableRow.objects.iter_by_user(self.suffolk_user))
        self.assertEqual(len(fixture_items), 1)
        self.assertEqual(self._get_value(fixture_items[0], 'cost'), '8')
        self.assertEqual(self._get_value(fixture_items[0], 'location_name'), 'Suffolk')

    def test_sees_own_fixture_and_parent_fixture(self):
        fixture_items = list(LookupTableRow.objects.iter_by_user(self.boston_user))
        self.assertItemsEqual(
            [(self._get_value(item, 'cost'), self._get_value(item, 'location_name'))
             for item in fixture_items],
            [('8', 'Suffolk'), ('10', 'Boston')]
        )

    def test_has_no_assigned_fixture(self):
        fixture_items = list(LookupTableRow.objects.iter_by_user(self.middlesex_user))
        self.assertEqual(len(fixture_items), 0)

from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.fixtures.dbaccessors import get_fixture_data_types_in_domain
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField, \
    FixtureDataItem, FieldList, FixtureItemField, FixtureOwnership
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

        data_type = FixtureDataType(
            domain=cls.domain,
            tag=cls.tag,
            name="Big Mac Index",
            fields=[
                FixtureTypeField(field_name="cost", properties=[]),
                FixtureTypeField(field_name="region", properties=[]),
            ],
            item_attributes=[],
        )
        data_type.save()

        def make_data_item(location_name, cost):
            """Make a fixture data item and assign it to location_name"""
            data_item = FixtureDataItem(
                domain=cls.domain,
                data_type_id=data_type.get_id,
                fields={
                    "cost": FieldList(
                        field_list=[FixtureItemField(
                            field_value=cost,
                            properties={},
                        )]
                    ),
                    "location_name": FieldList(
                        field_list=[FixtureItemField(
                            field_value=location_name,
                            properties={},
                        )]
                    ),
                },
                item_attributes={},
            )
            data_item.save()

            FixtureOwnership(
                domain=cls.domain,
                owner_id=cls.locations[location_name].location_id,
                owner_type='location',
                data_item_id=data_item.get_id
            ).save()

        make_data_item('Suffolk', '8')
        make_data_item('Boston', '10')
        make_data_item('Somerville', '7')
        get_fixture_data_types_in_domain.clear(cls.domain)

        cls.no_location_user = CommCareUser.create(cls.domain, 'no_location', '***')
        cls.suffolk_user = CommCareUser.create(cls.domain, 'guy-from-suffolk', '***')
        cls.suffolk_user.set_location(cls.locations['Suffolk'])
        cls.boston_user = CommCareUser.create(cls.domain, 'guy-from-boston', '***')
        cls.boston_user.set_location(cls.locations['Boston'])
        cls.middlesex_user = CommCareUser.create(cls.domain, 'guy-from-middlesex', '***')
        cls.middlesex_user.set_location(cls.locations['Middlesex'])

    @staticmethod
    def _get_value(fixture_item, field_name):
        return fixture_item.fields[field_name].field_list[0].field_value

    def test_sees_fixture_at_own_location(self):
        fixture_items = FixtureDataItem.by_user(self.suffolk_user)
        self.assertEqual(len(fixture_items), 1)
        self.assertEqual(self._get_value(fixture_items[0], 'cost'), '8')
        self.assertEqual(self._get_value(fixture_items[0], 'location_name'), 'Suffolk')

    def test_sees_own_fixture_and_parent_fixture(self):
        fixture_items = FixtureDataItem.by_user(self.boston_user)
        self.assertItemsEqual(
            [(self._get_value(item, 'cost'), self._get_value(item, 'location_name'))
             for item in fixture_items],
            [('8', 'Suffolk'), ('10', 'Boston')]
        )

    def test_has_no_assigned_fixture(self):
        fixture_items = FixtureDataItem.by_user(self.middlesex_user)
        self.assertEqual(len(fixture_items), 0)

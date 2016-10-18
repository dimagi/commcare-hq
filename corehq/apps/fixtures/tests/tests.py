# -*- coding: utf-8 -*-
from xml.etree import ElementTree

from django.test import TestCase, SimpleTestCase

from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.fixtures.dbaccessors import (
    get_number_of_fixture_data_types_in_domain,
    get_fixture_data_types_in_domain,
)
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership, FixtureTypeField, \
    FixtureItemField, FieldList
from corehq.apps.fixtures.utils import is_identifier_invalid
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


class DBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'fixture-dbaccessors'
        cls.data_types = [
            FixtureDataType(domain=cls.domain, tag='a'),
            FixtureDataType(domain=cls.domain, tag='b'),
            FixtureDataType(domain=cls.domain, tag='c'),
            FixtureDataType(domain='other-domain', tag='x'),
        ]
        FixtureDataType.get_db().bulk_save(cls.data_types)
        get_fixture_data_types_in_domain.clear(cls.domain)

    @classmethod
    def tearDownClass(cls):
        FixtureDataType.get_db().bulk_delete(cls.data_types)
        get_fixture_data_types_in_domain.clear(cls.domain)

    def test_get_number_of_fixture_data_types_in_domain(self):
        self.assertEqual(
            get_number_of_fixture_data_types_in_domain(self.domain),
            len([data_type for data_type in self.data_types
                 if data_type.domain == self.domain])
        )

    def test_get_fixture_data_types_in_domain(self):
        expected = [data_type.to_json() for data_type in self.data_types if data_type.domain == self.domain]
        actual = [o.to_json() for o in get_fixture_data_types_in_domain(self.domain)]
        self.assertItemsEqual(actual, expected)


class FieldNameCleanTest(TestCase):
    """Makes sure that bad characters are properly escaped in the xml
    """

    def setUp(self):
        self.domain = 'dirty-fields'

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag='dirty_fields',
            name="Dirty Fields",
            fields=[
                FixtureTypeField(
                    field_name="will/crash",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="space cadet",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="yes\\no",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="<with>",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="<crazy / combo><d",
                    properties=[]
                )
            ],
            item_attributes=[],
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
                "will/crash": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="yep",
                            properties={}
                        )
                    ]
                ),
                "space cadet": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="major tom",
                            properties={}
                        )
                    ]
                ),
                "yes\\no": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="no, duh",
                            properties={}
                        )
                    ]
                ),
                "<with>": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="so fail",
                            properties={}
                        )
                    ]
                ),
                "<crazy / combo><d": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="just why",
                            properties={}
                        )
                    ]
                ),
                "xmlbad": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="badxml",
                            properties={}
                        )
                    ]
                )
            },
            item_attributes={},
        )
        self.data_item.save()

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()

    def test_cleaner(self):
        check_xml_line_by_line(self, """
        <dirty_fields>
            <will_crash>yep</will_crash>
            <space_cadet>major tom</space_cadet>
            <yes_no>no, duh</yes_no>
            <_with_>so fail</_with_>
            <_crazy___combo__d>just why</_crazy___combo__d>
        </dirty_fields>
        """, ElementTree.tostring(self.data_item.to_xml()))


class FieldNameValidationTest(SimpleTestCase):
    """Makes sure that the field name validator does what's expected.
    """

    def test_slash(self):
        bad_name = "will/crash"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_space(self):
        bad_name = "space cadet"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_xml(self):
        bad_name = "xml_and_more"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_backslash(self):
        bad_name = "space\\cadet"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_brackets(self):
        bad_name = "<space>"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_combo(self):
        bad_name = "<space>\<dadgg sd"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_starts_with_number(self):
        bad_name = "0hello"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_unicode(self):
        bad_name = u"ﾉｲ丂 ﾑ ｲ尺ﾑｱ! \_(ツ)_/¯"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_good(self):
        good_name = "fooxmlbar0123"
        self.assertFalse(is_identifier_invalid(good_name))

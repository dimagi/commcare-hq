from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.xml import V2
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.dbaccessors import \
    get_number_of_fixture_data_types_in_domain, \
    get_fixture_data_types_in_domain
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership, FixtureTypeField, \
    FixtureItemField, FieldList
from corehq.apps.fixtures.exceptions import FixtureVersionError
from corehq.apps.fixtures.utils import is_field_name_invalid
from corehq.apps.users.models import CommCareUser
from django.test import TestCase, SimpleTestCase


class FixtureDataTest(TestCase):
    def setUp(self):
        self.domain = 'qwerty'
        self.tag = "district"

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag=self.tag,
            name="Districts",
            fields=[
                FixtureTypeField(
                    field_name="state_name",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="district_name",
                    properties=["lang"]
                ),
                FixtureTypeField(
                    field_name="district_id",
                    properties=[]
                )            
            ],
            item_attributes=[],
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields= {
                "state_name": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="Delhi_state",
                            properties={}
                        )
                    ]
                ),
                "district_name": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="Delhi_in_HIN",
                            properties={"lang": "hin"}
                        ),
                        FixtureItemField(
                            field_value="Delhi_in_ENG",
                            properties={"lang": "eng"}
                        )
                    ]
                ),
                "district_id": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="Delhi_id",
                            properties={}
                        )
                    ]
                )
            },
            item_attributes={},
        )
        self.data_item.save()

        self.user = CommCareUser.create(self.domain, 'to_delete', '***')

        self.fixture_ownership = FixtureOwnership(
            domain=self.domain,
            owner_id=self.user.get_id,
            owner_type='user',
            data_item_id=self.data_item.get_id
        )
        self.fixture_ownership.save()

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()
        self.user.delete()
        self.fixture_ownership.delete()

    def test_xml(self):
        check_xml_line_by_line(self, """
        <district>
            <state_name>Delhi_state</state_name>
            <district_name lang="hin">Delhi_in_HIN</district_name>
            <district_name lang="eng">Delhi_in_ENG</district_name>
            <district_id>Delhi_id</district_id>
        </district>
        """, ElementTree.tostring(self.data_item.to_xml()))

    def test_ownership(self):
        self.assertItemsEqual([self.data_item.get_id], FixtureDataItem.by_user(self.user, wrap=False))
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

        fixture, = fixturegenerators.item_lists(self.user, V2)

        check_xml_line_by_line(self, """
        <fixture id="item-list:district" user_id="%s">
            <district_list>
                <district>
                    <state_name>Delhi_state</state_name>
                    <district_name lang="hin">Delhi_in_HIN</district_name>
                    <district_name lang="eng">Delhi_in_ENG</district_name>
                    <district_id>Delhi_id</district_id>
                </district>
            </district_list>            
        </fixture>
        """ % self.user.user_id, ElementTree.tostring(fixture))

        self.data_item.remove_user(self.user)
        self.assertItemsEqual([], self.data_item.get_all_users())

        self.fixture_ownership = self.data_item.add_user(self.user)
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

    def test_get_indexed_items(self):
        with self.assertRaises(FixtureVersionError):
            fixtures = FixtureDataItem.get_indexed_items(self.domain,
                self.tag, 'state_name')
            delhi_id = fixtures['Delhi_state']['district_id']
            self.assertEqual(delhi_id, 'Delhi_id')


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

    @classmethod
    def tearDownClass(cls):
        FixtureDataType.get_db().bulk_delete(cls.data_types)

    def test_get_number_of_fixture_data_types_in_domain(self):
        self.assertEqual(
            get_number_of_fixture_data_types_in_domain(self.domain),
            len([data_type for data_type in self.data_types
                 if data_type.domain == self.domain])
        )

    def test_get_fixture_data_types_in_domain(self):
        self.assertItemsEqual(
            [o.to_json()
             for o in get_fixture_data_types_in_domain(self.domain)],
            [data_type.to_json() for data_type in self.data_types
             if data_type.domain == self.domain]
        )


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
        self.assertTrue(is_field_name_invalid(bad_name))

    def test_space(self):
        bad_name = "space cadet"
        self.assertTrue(is_field_name_invalid(bad_name))

    def test_backslash(self):
        bad_name = "space\\cadet"
        self.assertTrue(is_field_name_invalid(bad_name))

    def test_brackets(self):
        bad_name = "<space>"
        self.assertTrue(is_field_name_invalid(bad_name))

    def test_combo(self):
        bad_name = "<space>\<dadgg sd"
        self.assertTrue(is_field_name_invalid(bad_name))

    def test_good(self):
        good_name = "foobar"
        self.assertFalse(is_field_name_invalid(good_name))

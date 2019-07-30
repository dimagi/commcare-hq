from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree

import six
from django.test import TestCase

from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.phone.tests.utils import call_fixture_generator as call_fixture_generator_raw
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.dbaccessors import delete_all_fixture_data_types, \
    get_fixture_data_types_in_domain
from corehq.apps.fixtures.exceptions import FixtureVersionError
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField, \
    FixtureDataItem, FieldList, FixtureItemField, FixtureOwnership, FIXTURE_BUCKET
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.blobs import get_blob_db


def call_fixture_generator(user):
    return [ElementTree.fromstring(f) if isinstance(f, bytes) else f
            for f in call_fixture_generator_raw(fixturegenerators.item_lists, user)]


class FixtureDataTest(TestCase):

    def setUp(self):
        super(FixtureDataTest, self).setUp()
        self.domain = 'qwerty'
        self.tag = "district"
        delete_all_users()
        delete_all_fixture_data_types()

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
                ),
            ],
            item_attributes=[],
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
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
        get_fixture_data_types_in_domain.clear(self.domain)

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()
        self.user.delete()
        self.fixture_ownership.delete()
        delete_all_users()
        delete_all_fixture_data_types()
        get_fixture_data_types_in_domain.clear(self.domain)
        get_blob_db().delete(key=FIXTURE_BUCKET + '/' + self.domain)
        super(FixtureDataTest, self).tearDown()

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

        fixture, = call_fixture_generator(self.user.to_ota_restore_user())

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

    def test_fixture_removal(self):
        """
        An empty fixture list should be generated for each fixture that the
        use does not have access to (within the domain).
        """

        self.data_item.remove_user(self.user)

        fixtures = call_fixture_generator(self.user.to_ota_restore_user())
        self.assertEqual(1, len(fixtures))
        check_xml_line_by_line(
            self,
            """
            <fixture id="item-list:district" user_id="{}">
                <district_list />
            </fixture>
            """.format(self.user.user_id),
            ElementTree.tostring(fixtures[0])
        )

        self.fixture_ownership = self.data_item.add_user(self.user)

    def test_get_indexed_items(self):
        with self.assertRaises(FixtureVersionError):
            fixtures = FixtureDataItem.get_indexed_items(
                self.domain, self.tag, 'state_name')
            delhi_id = fixtures['Delhi_state']['district_id']
            self.assertEqual(delhi_id, 'Delhi_id')

    def test_get_item_by_field_value(self):
        self.assertEqual(
            FixtureDataItem.by_field_value(self.domain, self.data_type, 'state_name', 'Delhi_state').one().get_id,
            self.data_item.get_id
        )

    def test_fixture_is_indexed(self):
        self.data_type.fields[2].is_indexed = True  # Set "district_id" as indexed
        self.data_type.save()

        fixtures = call_fixture_generator(self.user.to_ota_restore_user())
        self.assertEqual(len(fixtures), 2)
        check_xml_line_by_line(
            self,
            """
            <fixtures>
                <schema id="item-list:district">
                    <indices>
                        <index>district_id</index>
                    </indices>
                </schema>
                <fixture id="item-list:district" indexed="true" user_id="{}">
                    <district_list>
                        <district>
                            <state_name>Delhi_state</state_name>
                            <district_name lang="hin">Delhi_in_HIN</district_name>
                            <district_name lang="eng">Delhi_in_ENG</district_name>
                            <district_id>Delhi_id</district_id>
                        </district>
                    </district_list>
                </fixture>
            </fixtures>
            """.format(self.user.user_id),
            """
            <fixtures>
                {}
                {}
            </fixtures>
            """.format(*[ElementTree.tostring(fixture).decode('utf-8') for fixture in fixtures])
        )

    def test_empty_data_types(self):
        empty_data_type = FixtureDataType(
            domain=self.domain,
            tag='blank',
            name="blank",
            fields=[
                FixtureTypeField(
                    field_name="name",
                    properties=[]
                ),
            ],
            item_attributes=[],
        )
        empty_data_type.save()
        self.addCleanup(empty_data_type.delete)
        get_fixture_data_types_in_domain.clear(self.domain)

        fixtures = call_fixture_generator(self.user.to_ota_restore_user())
        self.assertEqual(2, len(fixtures))
        check_xml_line_by_line(
            self,
            """
            <f>
            <fixture id="item-list:blank" user_id="{0}">
              <blank_list/>
            </fixture>
            <fixture id="item-list:district" user_id="{0}">
              <district_list>
                <district>
                  <state_name>Delhi_state</state_name>
                  <district_name lang="hin">Delhi_in_HIN</district_name>
                  <district_name lang="eng">Delhi_in_ENG</district_name>
                  <district_id>Delhi_id</district_id>
                </district>
              </district_list>
            </fixture>
            </f>
            """.format(self.user.user_id),
            '<f>{}\n{}\n</f>'.format(*[ElementTree.tostring(fixture).decode('utf-8') for fixture in fixtures])
        )

    def test_user_data_type_with_item(self):
        cookie = self.make_data_type("cookie", is_global=False)
        latte = self.make_data_type("latte", is_global=True)
        self.make_data_item(cookie, "2.50")
        self.make_data_item(latte, "5.75")

        fixtures = call_fixture_generator(self.user.to_ota_restore_user())
        # make sure each fixture is there, and only once
        self.assertEqual(
            [item.attrib['id'] for item in fixtures],
            [
                'item-list:latte-index',
                'item-list:cookie-index',
                'item-list:district',
            ],
        )

    def test_empty_user_data_types(self):
        self.make_data_type("cookie", is_global=False)

        fixtures = call_fixture_generator(self.user.to_ota_restore_user())
        # make sure each fixture is there, and only once
        self.assertEqual(
            [item.attrib['id'] for item in fixtures],
            [
                'item-list:cookie-index',
                'item-list:district',
            ],
        )

    def test_cached_global_fixture_user_id(self):
        sandwich = self.make_data_type("sandwich", is_global=True)
        self.make_data_item(sandwich, "7.39")
        frank = self.user.to_ota_restore_user()
        sammy = CommCareUser.create(self.domain, 'sammy', '***').to_ota_restore_user()

        fixtures = call_fixture_generator(frank)
        self.assertEqual({item.attrib['user_id'] for item in fixtures}, {frank.user_id})
        self.assertTrue(get_blob_db().exists(key=FIXTURE_BUCKET + '/' + self.domain))

        fixtures = call_fixture_generator(sammy)
        self.assertEqual({item.attrib['user_id'] for item in fixtures}, {sammy.user_id})

    def make_data_type(self, name, is_global):
        data_type = FixtureDataType(
            domain=self.domain,
            tag="{}-index".format(name),
            is_global=is_global,
            name=name.title(),
            fields=[
                FixtureTypeField(field_name="cost", properties=[]),
            ],
            item_attributes=[],
        )
        data_type.save()
        self.addCleanup(data_type.delete)
        return data_type

    def make_data_item(self, data_type, cost):
        data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=data_type._id,
            fields={
                "cost": FieldList(
                    field_list=[FixtureItemField(
                        field_value=cost,
                        properties={},
                    )]
                ),
            },
            item_attributes={},
        )
        data_item.save()
        self.addCleanup(data_item.delete)
        return data_item


class TestFixtureOrdering(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestFixtureOrdering, cls).setUpClass()
        cls.domain = "TestFixtureOrdering"
        cls.user = CommCareUser.create(cls.domain, 'george', '***')

        cls.data_type = FixtureDataType(
            domain=cls.domain,
            tag="houses-of-westeros",
            is_global=True,
            name="Great Houses of Westeros",
            fields=[
                FixtureTypeField(field_name="name", properties=[]),
                FixtureTypeField(field_name="seat", properties=[]),
                FixtureTypeField(field_name="sigil", properties=[]),
            ],
            item_attributes=[],
        )
        cls.data_type.save()

        cls.data_items = [
            cls._make_data_item(4, "Tyrell", "Highgarden", "Rose"),
            cls._make_data_item(6, "Martell", "Sunspear", "Sun and Spear"),
            cls._make_data_item(3, "Lannister", "Casterly Rock", "Lion"),
            cls._make_data_item(1, "Targaryen", "Dragonstone", "Dragon"),
            cls._make_data_item(5, "Tully", "Riverrun", "Trout"),
            cls._make_data_item(2, "Stark", "Winterfell", "Direwolf"),
            cls._make_data_item(7, "Baratheon", "Storm's End", "Stag"),
        ]

    @classmethod
    def _make_data_item(cls, sort_key, name, seat, sigil):
        def field_list(value):
            return FieldList(field_list=[FixtureItemField(field_value=value, properties={})])

        data_item = FixtureDataItem(
            domain=cls.domain,
            data_type_id=cls.data_type._id,
            fields={
                "name": field_list(name),
                "seat": field_list(seat),
                "sigil": field_list(sigil),
            },
            item_attributes={},
            sort_key=sort_key,
        )
        data_item.save()
        return data_item

    @classmethod
    def tearDownClass(cls):
        for data_item in cls.data_items:
            data_item.delete()
        cls.data_type.delete()
        cls.user.delete()
        super(TestFixtureOrdering, cls).tearDownClass()

    def test_fixture_order(self):
        (fixture,) = call_fixture_generator(self.user.to_ota_restore_user())
        rows = fixture.getchildren()[0].getchildren()
        actual_names = [row.getchildren()[0].text for row in rows]
        self.assertEqual(
            ["Targaryen", "Stark", "Lannister", "Tyrell", "Tully", "Martell", "Baratheon"],
            actual_names
        )

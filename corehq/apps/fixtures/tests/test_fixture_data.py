from xml.etree import cElementTree as ElementTree
from datetime import datetime

from django.test import TestCase
from django.conf import settings

from casexml.apps.phone.models import SimplifiedSyncLog
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.phone.tests.utils import \
    call_fixture_generator as call_fixture_generator_raw

from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.models import (
    fixture_bucket,
    Field,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import CommCareUser
from corehq.blobs import get_blob_db
from corehq.blobs.tests.util import TemporaryS3BlobDB


def call_fixture_generator(user, last_sync=None):
    raw = call_fixture_generator_raw(fixturegenerators.item_lists, user,
                                    last_sync=last_sync)
    res = []
    for f in raw:
        if isinstance(f, bytes):
            wrapped_f = b'<root>' + f + b'</root>'
            root = ElementTree.fromstring(wrapped_f)
            for child in root:
                res.append(child)
        else:
            res.append(f)
    return res


class FixtureDataTest(TestCase):

    def setUp(self):
        super(FixtureDataTest, self).setUp()
        self.domain = 'qwerty'
        self.tag = "district"

        self.data_type = LookupTable(
            domain=self.domain,
            tag=self.tag,
            description="Districts",
            fields=[
                TypeField(name="state_name"),
                TypeField(name="district_name", properties=["lang"]),
                TypeField(name="district_id"),
            ],
            item_attributes=[],
        )
        self.data_type.save()
        self.addCleanup(get_blob_db().delete, key=fixture_bucket(self.data_type.id, self.domain))

        self.data_item = LookupTableRow(
            domain=self.domain,
            table_id=self.data_type.id,
            fields={
                "state_name": [
                    Field(value="Delhi_state")
                ],
                "district_name": [
                    Field(value="Delhi_in_HIN", properties={"lang": "hin"}),
                    Field(value="Delhi_in_ENG", properties={"lang": "eng"})
                ],
                "district_id": [
                    Field(value="Delhi_id")
                ]
            },
            item_attributes={},
            sort_key=0,
        )
        self.data_item.save()

        self.user = CommCareUser.create(self.domain, 'to_delete', '***', None, None)
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

        self.ownership = LookupTableRowOwner(
            domain=self.domain,
            owner_id=self.user.get_id,
            owner_type=OwnerType.User,
            row_id=self.data_item.id,
        )
        self.ownership.save()

        self.sync_log = SimplifiedSyncLog(
            date=datetime.utcnow(),
            domain=self.domain,
            user_id=self.user.user_id,
            build_id='some-build-id'
        )
        self.sync_log.save()

    def test_xml(self):
        check_xml_line_by_line(self, """
        <district>
            <state_name>Delhi_state</state_name>
            <district_name lang="hin">Delhi_in_HIN</district_name>
            <district_name lang="eng">Delhi_in_ENG</district_name>
            <district_id>Delhi_id</district_id>
        </district>
        """, ElementTree.tostring(fixturegenerators.item_lists.to_xml(
            self.data_item, self.data_type), encoding='utf-8'))

    def test_ownership(self):
        row_ids = [r.id for r in LookupTableRow.objects.iter_by_user(self.user)]
        self.assertItemsEqual([self.data_item.id], row_ids)

        fixture, = call_fixture_generator(self.user.to_ota_restore_user(self.domain))

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
        """ % self.user.user_id, ElementTree.tostring(fixture, encoding='utf-8'))

    def test_fixture_removal(self):
        """
        An empty fixture list should be generated for each fixture that the
        use does not have access to (within the domain).
        """
        self.ownership.delete()
        self.ownership = None

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
        self.assertEqual(1, len(fixtures))
        check_xml_line_by_line(
            self,
            """
            <fixture id="item-list:district" user_id="{}">
                <district_list />
            </fixture>
            """.format(self.user.user_id),
            ElementTree.tostring(fixtures[0], encoding='utf-8')
        )

    def test_get_item_by_field_value(self):
        self.assertEqual(
            LookupTableRow.objects.with_value(
                self.domain, self.data_type.id, 'state_name', 'Delhi_state').get().id,
            self.data_item.id
        )

    def test_fixture_is_indexed(self):
        self.data_type.fields[2].is_indexed = True  # Set "district_id" as indexed
        self.data_type.save()

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
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
            """.format(*[ElementTree.tostring(fixture, encoding='utf-8').decode('utf-8') for fixture in fixtures])
        )

    def test_empty_data_types(self):
        empty_data_type = LookupTable(
            domain=self.domain,
            tag='blank',
            description="blank",
            fields=[TypeField(name="name")],
            item_attributes=[],
        )
        empty_data_type.save()

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
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
            '<f>{}\n{}\n</f>'.format(*[
                ElementTree.tostring(fixture, encoding='utf-8').decode('utf-8')
                for fixture in fixtures
            ])
        )

    def test_user_data_type_with_item(self):
        cookie = self.make_data_type("cookie", is_global=False)
        latte = self.make_data_type("latte", is_global=True)
        self.make_data_item(cookie, "2.50")
        self.make_data_item(latte, "5.75")

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
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

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
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
        frank = self.user.to_ota_restore_user(self.domain)
        sammy_ = CommCareUser.create(self.domain, 'sammy', '***', None, None)
        self.addCleanup(sammy_.delete, self.domain, deleted_by=None)
        sammy = sammy_.to_ota_restore_user(self.domain)

        fixtures = call_fixture_generator(frank)
        self.assertEqual({item.attrib['user_id'] for item in fixtures}, {frank.user_id})
        self.assertTrue(get_blob_db().exists(key=fixture_bucket(sandwich.id, self.domain)))

        fixtures = call_fixture_generator(sammy)
        self.assertEqual({item.attrib['user_id'] for item in fixtures}, {sammy.user_id})

    def test_indexed_global_fixture(self):
        sandwich = self.make_data_type("sandwich", is_global=True)
        sandwich.fields[0].is_indexed = True
        sandwich.save()
        self.make_data_item(sandwich, "7.39")

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
        self.assertEqual(
            [(node.tag, node.attrib['id']) for node in fixtures],
            [
                ('schema', 'item-list:sandwich-index'),
                ('fixture', 'item-list:sandwich-index'),
                ('fixture', 'item-list:district'),
            ]
        )

    def test_simulate_s3_blob(self):
        config = settings.S3_BLOB_DB_SETTINGS
        db = TemporaryS3BlobDB(config)
        self.addCleanup(db.close)

        sandwich = self.make_data_type("sandwich", is_global=True)
        sandwich.save()
        self.make_data_item(sandwich, "7.39")

        fixtures = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
        self.assertEqual(
            [(node.tag, node.attrib['id']) for node in fixtures],
            [
                ('fixture', 'item-list:sandwich-index'),
                ('fixture', 'item-list:district'),
            ]
        )

    def test_include_fixture_when_data_type_modified(self):
        fixture = call_fixture_generator(self.user.to_ota_restore_user(self.domain), self.sync_log)
        self.assertEqual(len(fixture), 0)

        self.data_type.save()
        fixture, = call_fixture_generator(self.user.to_ota_restore_user(self.domain), self.sync_log)
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
        """ % self.user.user_id, ElementTree.tostring(fixture, encoding='utf-8'))

    def test_include_fixture_when_cache_is_cleared(self):
        fixture = call_fixture_generator(self.user.to_ota_restore_user(self.domain), self.sync_log)
        self.assertEqual(len(fixture), 0)

        clear_fixture_cache(self.domain, [self.data_type.id])
        fixture, = call_fixture_generator(self.user.to_ota_restore_user(self.domain), self.sync_log)
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
        """ % self.user.user_id, ElementTree.tostring(fixture, encoding='utf-8'))

    def make_data_type(self, name, is_global):
        data_type = LookupTable(
            domain=self.domain,
            tag="{}-index".format(name),
            is_global=is_global,
            description=name.title(),
            fields=[
                TypeField(name="cost", properties=[]),
            ],
            item_attributes=[],
        )
        data_type.save()
        self.addCleanup(get_blob_db().delete, key=fixture_bucket(data_type.id, self.domain))
        return data_type

    def make_data_item(self, data_type, cost):
        data_item = LookupTableRow(
            domain=self.domain,
            table_id=data_type.id,
            fields={"cost": [Field(value=cost)]},
            item_attributes={},
            sort_key=0,
        )
        data_item.save()
        return data_item


class TestFixtureOrdering(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestFixtureOrdering, cls).setUpClass()
        cls.domain = "TestFixtureOrdering"
        cls.user = CommCareUser.create(cls.domain, 'george', '***', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)

        cls.data_type = LookupTable(
            domain=cls.domain,
            tag="houses-of-westeros",
            is_global=True,
            description="Great Houses of Westeros",
            fields=[
                TypeField(name="name"),
                TypeField(name="seat"),
                TypeField(name="sigil"),
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
        data_item = LookupTableRow(
            domain=cls.domain,
            table_id=cls.data_type.id,
            fields={
                "name": [Field(value=name)],
                "seat": [Field(value=seat)],
                "sigil": [Field(value=sigil)],
            },
            item_attributes={},
            sort_key=sort_key,
        )
        data_item.save()
        return data_item

    def test_fixture_order(self):
        (fixture,) = call_fixture_generator(self.user.to_ota_restore_user(self.domain))
        actual_names = [row[0].text for row in fixture[0]]
        self.assertEqual(
            ["Targaryen", "Stark", "Lannister", "Tyrell", "Tully", "Martell", "Baratheon"],
            actual_names
        )

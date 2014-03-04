from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.xml import V2
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership, FixtureTypeField, \
    FixtureItemField, FieldList
from corehq.apps.fixtures.views import update_tables
from corehq.apps.fixtures.exceptions import FixtureVersionError
from corehq.apps.users.models import CommCareUser
from django.test import TestCase

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
            ]
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
            }
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

        fixture, = fixturegenerators.item_lists(self.user, version=V2, last_sync=None)

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

    def test_edit_type(self):
        sample_test_patch = {
            "tag": "change_to_grow",
            "view_link": "/a/hqtest/fixtures/view_lookup_tables/?table_id:3345172444aebee6a75cee1a07fb30d6",
            "fields": {
                "state_name": {"update": "st_name"},
                "district_name": {},
                "district_id": {"remove": 1},
                "new_field": {"is_new": 1}
            }
        }
        old_type = self.data_type
        old_item = self.data_item
       
        update_tables(self.domain, self.data_type.get_id, test_patch=sample_test_patch)
    
        self.data_type = FixtureDataType.get(self.data_type.get_id)
        self.data_item = FixtureDataItem.get(self.data_item.get_id)
        new_type = self.data_type
        new_item = self.data_item
        new_type_fields = [field.field_name for field in self.data_type.fields]
        new_item_fields = new_item.fields.keys()
        updated_fields = ["st_name", "district_name", "new_field"]

        self.assertEqual(self.data_type.tag, "change_to_grow")
        self.assertItemsEqual(new_type_fields, updated_fields)
        self.assertItemsEqual(new_item_fields, updated_fields)
        self.assertItemsEqual(self.data_item.fields.keys(), new_item_fields)

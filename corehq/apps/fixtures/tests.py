from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.xml import V2
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


class FixtureDataTest(TestCase):
    def setUp(self):
        self.domain = 'qwerty'
        self.tag = "contact"

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag=self.tag,
            name="Contact",
            fields=['name', 'number']
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
                'name': 'John',
                'number': '+15555555555'
            }
        )
        self.data_item.save()

        for name, number in [('Michael', '+16666666666'),
            ('Eric', '+17777777777')]:
            data_item = FixtureDataItem(
                domain=self.domain,
                data_type_id=self.data_type.get_id,
                fields={
                    'name': name,
                    'number': number,
                }
            )
            data_item.save()

        self.user = CommCareUser.create(self.domain, 'rudolph', '***')

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
        <contact>
            <name>John</name>
            <number>+15555555555</number>
        </contact>
        """, ElementTree.tostring(self.data_item.to_xml()))

    def test_ownership(self):
        self.assertItemsEqual([self.data_item.get_id], FixtureDataItem.by_user(self.user, wrap=False))
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

        fixture, = fixturegenerators.item_lists(self.user, version=V2, last_sync=None)

        check_xml_line_by_line(self, """
        <fixture id="item-list:contact" user_id="%s">
            <contact_list>
                <contact>
                    <name>John</name>
                    <number>+15555555555</number>
                </contact>
            </contact_list>
        </fixture>
        """ % self.user.user_id, ElementTree.tostring(fixture))

        self.data_item.remove_user(self.user)
        self.assertItemsEqual([], self.data_item.get_all_users())

        self.fixture_ownership = self.data_item.add_user(self.user)
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

    def test_get_indexed_items(self):
        fixtures = FixtureDataItem.get_indexed_items(self.domain,
            self.tag, 'name')
        john_num = fixtures['John']['number']
        self.assertEqual(john_num, '+15555555555')
from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership
from corehq.apps.users.models import CommCareUser
from django.test import TestCase

class FixtureDataTest(TestCase):
    def setUp(self):
        self.domain = 'qwerty'

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag="contact",
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
        self.assertItemsEqual([self.user.get_id], self.data_item.get_users(wrap=False))

        self.data_item.remove_user(self.user)
        self.assertItemsEqual([], self.data_item.get_users())

        self.fixture_ownership = self.data_item.add_user(self.user)
        self.assertItemsEqual([self.user.get_id], self.data_item.get_users(wrap=False))

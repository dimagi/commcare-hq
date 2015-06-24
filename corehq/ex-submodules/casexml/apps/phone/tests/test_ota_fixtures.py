from xml.etree import ElementTree
from django.test import TestCase
from casexml.apps.case.xml import V2, V1
from casexml.apps.phone.fixtures import generator
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import (
    FixtureDataType, FixtureTypeField,
    FixtureDataItem, FieldList, FixtureItemField
)
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from casexml.apps.case.tests.util import check_xml_line_by_line

DOMAIN = 'fixture-test'


class OtaFixtureTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain.get_or_create_with_name(DOMAIN, is_active=True)
        cls.user = CommCareUser.create(DOMAIN, 'bob', 'mechanic')
        cls.group1 = Group(domain=DOMAIN, name='group1', case_sharing=True, users=[cls.user._id])
        cls.group1.save()
        cls.group2 = Group(domain=DOMAIN, name='group2', case_sharing=True, users=[cls.user._id])
        cls.group2.save()

        cls.data_type = FixtureDataType(
            domain=DOMAIN,
            tag="district",
            name="Districts",
            fields=[FixtureTypeField(field_name="state_name", properties=[])],
            item_attributes=[],
            is_global=True
        )
        cls.data_type.save()

        cls.data_item = FixtureDataItem(
            domain=DOMAIN,
            data_type_id=cls.data_type.get_id,
            fields={
                "state_name": FieldList(
                    field_list=[FixtureItemField(field_value="Delhi_state", properties={})]
                )
            },
            item_attributes={},
        )
        cls.data_item.save()

        cls.casexml_user = cls.user.to_casexml_user()

    @classmethod
    def tearDownClass(cls):
        for group in Group.by_domain(DOMAIN):
            group.delete()
        for user in CommCareUser.all():
            user.delete()

        cls.data_type.delete()
        cls.data_item.delete()
        cls.domain.delete()

    def _check_fixture(self, fixture_xml, has_groups=True, has_item_lists=True):
        fixtures = [ElementTree.tostring(xml) for xml in fixture_xml]
        expected_len = sum([has_groups, has_item_lists])
        self.assertEqual(len(fixtures), expected_len)

        if has_groups:
            expected = _get_group_fixture(self.user.get_id, [self.group1, self.group2])
            check_xml_line_by_line(self, expected, fixtures[0])

        if has_item_lists:
            expected = _get_item_list_fixture(self.user.get_id, self.data_type.tag, self.data_item)
            check_xml_line_by_line(self, expected, fixtures[-1])

    def test_fixture_gen_v1(self):
        fixture_xml = generator.get_fixtures(self.casexml_user, version=V1)
        self.assertEqual(fixture_xml, [])

    def test_basic_fixture_generation(self):
        fixture_xml = generator.get_fixtures(self.casexml_user, version=V2)
        self._check_fixture(fixture_xml)

    def test_fixtures_by_group(self):
        fixture_xml = generator.get_fixtures(self.casexml_user, version=V2, group='case')
        self.assertEqual(list(fixture_xml), [])

        fixture_xml = generator.get_fixtures(self.casexml_user, version=V2, group='standalone')
        self._check_fixture(fixture_xml)

    def test_fixtures_by_id(self):
        fixture_xml = generator.get_fixture_by_id('user-groups', self.casexml_user, version=V2)
        self._check_fixture(fixture_xml, has_item_lists=False)

        fixture_xml = generator.get_fixture_by_id('item-list', self.casexml_user, version=V2)
        self._check_fixture(fixture_xml, has_groups=False)

        fixture_xml = generator.get_fixture_by_id('user-locations', self.casexml_user, version=V2)
        self.assertEqual(list(fixture_xml), [])

        fixture_xml = generator.get_fixture_by_id('bad ID', self.casexml_user, version=V2)
        self.assertEqual(list(fixture_xml), [])


def _get_group_fixture(user_id, groups):
    groups = sorted(groups, key=lambda g: g.get_id)
    group_blocks = ["""
    <group id="{id}">
        <name>{name}</name>
    </group>
    """.format(id=group.get_id, name=group.name) for group in groups]

    groups_xml = """
    <groups>
        {}
    </groups>
    """.format(''.join(group_blocks)) if group_blocks else "<groups/>"

    return """
    <fixture id="user-groups" user_id="{user_id}">
        {groups}
    </fixture>
    """.format(user_id=user_id, groups=groups_xml)


def _get_item_list_fixture(user_id, tag, fixture_item):
    template = """
    <fixture id="item-list:{tag}" user_id="{user_id}">
      <district_list>
        {item_xml}
      </district_list>
    </fixture>
    """
    return template.format(
        user_id=user_id,
        tag=tag,
        item_xml=ElementTree.tostring(fixture_item.to_xml())
    )

from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree
from django.test import TestCase
from corehq.blobs import get_blob_db
from casexml.apps.phone.fixtures import generator
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import (
    FixtureDataType, FixtureTypeField,
    FixtureDataItem, FieldList, FixtureItemField,
    FIXTURE_BUCKET
)
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.form_processor.tests.utils import use_sql_backend

DOMAIN = 'fixture-test'
SA_PROVINCES = 'sa_provinces'
FR_PROVINCES = 'fr_provinces'


class OtaFixtureTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(OtaFixtureTest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(DOMAIN, is_active=True)
        cls.user = CommCareUser.create(DOMAIN, 'bob', 'mechanic')
        cls.group1 = Group(domain=DOMAIN, name='group1', case_sharing=True, users=[cls.user._id])
        cls.group1.save()
        cls.group2 = Group(domain=DOMAIN, name='group2', case_sharing=True, users=[cls.user._id])
        cls.group2.save()

        cls.item_lists = {
            SA_PROVINCES: make_item_lists(SA_PROVINCES, 'western cape'),
            FR_PROVINCES: make_item_lists(FR_PROVINCES, 'burgundy'),
        }

        cls.restore_user = cls.user.to_ota_restore_user()

    @classmethod
    def tearDownClass(cls):
        for group in Group.by_domain(DOMAIN):
            group.delete()
        delete_all_users()

        for _, item_list in cls.item_lists.items():
            item_list[0].delete()
            item_list[1].delete()

        get_blob_db().delete(DOMAIN, FIXTURE_BUCKET)
        cls.domain.delete()
        super(OtaFixtureTest, cls).tearDownClass()

    def _check_fixture(self, fixture_xml, has_groups=True, item_lists=None):
        fixture_xml = list(fixture_xml)
        item_lists = item_lists or []
        expected_len = sum([has_groups, len(item_lists)])
        self.assertEqual(len(fixture_xml), expected_len)

        if has_groups:
            expected = _get_group_fixture(self.user.get_id, [self.group1, self.group2])
            check_xml_line_by_line(self, expected, ElementTree.tostring(fixture_xml[0]))

        if item_lists:
            for i, item_list_tag in enumerate(item_lists):
                data_type, data_item = self.item_lists[item_list_tag]
                item_list_xml = [
                    ElementTree.tostring(fixture)
                    for fixture in fixture_xml if item_list_tag in fixture.attrib.get("id")
                ]
                self.assertEqual(len(item_list_xml), 1)

                expected = _get_item_list_fixture(self.user.get_id, data_type.tag, data_item)
                check_xml_line_by_line(self, expected, item_list_xml[0])

    def test_fixtures_by_id(self):
        fixture_xml = generator.get_fixture_by_id('user-groups', self.restore_user)
        self._check_fixture([fixture_xml])

        fixture_xml = generator.get_fixture_by_id('item-list:sa_provinces', self.restore_user)
        self._check_fixture([fixture_xml], has_groups=False, item_lists=[SA_PROVINCES])

        fixture_xml = generator.get_fixture_by_id('item-list:fr_provinces', self.restore_user)
        self._check_fixture([fixture_xml], has_groups=False, item_lists=[FR_PROVINCES])

        fixture_xml = generator.get_fixture_by_id('user-locations', self.restore_user)
        self.assertIsNone(fixture_xml)

        fixture_xml = generator.get_fixture_by_id('bad ID', self.restore_user)
        self.assertIsNone(fixture_xml)


@use_sql_backend
class OtaFixtureTestSQL(OtaFixtureTest):
    pass


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
      <{tag}_list>
        {item_xml}
      </{tag}_list>
    </fixture>
    """
    return template.format(
        user_id=user_id,
        tag=tag,
        item_xml=ElementTree.tostring(fixture_item.to_xml())
    )


def make_item_lists(tag, item_name):
    data_type = FixtureDataType(
        domain=DOMAIN,
        tag=tag,
        name="Provinces",
        fields=[FixtureTypeField(field_name="name", properties=[])],
        item_attributes=[],
        is_global=True
    )
    data_type.save()

    data_item = FixtureDataItem(
        domain=DOMAIN,
        data_type_id=data_type.get_id,
        fields={
            "name": FieldList(
                field_list=[FixtureItemField(field_value=item_name, properties={})]
            )
        },
        item_attributes={},
    )
    data_item.save()
    return data_type, data_item

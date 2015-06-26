from collections import namedtuple
from datetime import timedelta
from django.test import TestCase
from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.users.models import CommCareUser

DOMAIN = 't1'

FakeSyncLog = namedtuple('FakeSyncLog', 'date')


class GroupFixtureTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = CommCareUser.create(domain=DOMAIN, username='zombie1', password='***')

    def tearDown(self):
        from corehq.apps.groups.models import Group
        for group in Group.by_domain(DOMAIN):
            group.delete()

    def test_group_fixture(self):
        from corehq.apps.groups.models import Group

        user_id = self.user._id
        group = Group(domain=DOMAIN, name='walking dead', users=[user_id], case_sharing=True)
        group.save()

        fixture = self.user.get_group_fixture(None)
        self.assertIsNotNone(fixture)
        check_xml_line_by_line(self, _get_group_fixture(user_id, [group]), ElementTree.tostring(fixture))

    def test_group_fixture_case_sharing(self):
        from corehq.apps.groups.models import Group

        user_id = self.user._id
        group = Group(domain=DOMAIN, name='walking dead', users=[user_id], case_sharing=False)
        group.save()

        fixture = self.user.get_group_fixture(None)
        self.assertIsNotNone(fixture)
        check_xml_line_by_line(self, _get_group_fixture(user_id, []), ElementTree.tostring(fixture))

    def test_group_fixture_no_change(self):
        from corehq.apps.groups.models import Group

        user_id = self.user._id
        group = Group(domain=DOMAIN, name='walking dead', users=[user_id], case_sharing=True)
        group.save()

        # simulate last sync after most recent change to group
        last_sync_date = group.last_modified + timedelta(seconds=1)
        fixture = self.user.get_group_fixture(FakeSyncLog(date=last_sync_date))
        self.assertIsNone(fixture)

    def test_group_fixture_with_change(self):
        from corehq.apps.groups.models import Group

        user_id = self.user._id
        group = Group(domain=DOMAIN, name='walking dead', users=[user_id], case_sharing=True)
        group.save()

        # simulate last sync before most recent change to group
        last_sync_date = group.last_modified - timedelta(seconds=1)
        fixture = self.user.get_group_fixture(FakeSyncLog(date=last_sync_date))
        self.assertIsNotNone(fixture)
        check_xml_line_by_line(self, _get_group_fixture(user_id, [group]), ElementTree.tostring(fixture))

    def test_group_fixture_removed_user(self):
        from corehq.apps.groups.models import Group

        user_id = self.user._id
        group1 = Group(domain=DOMAIN, name='walking dead', users=[user_id], case_sharing=True)
        group1.save()
        group2 = Group(domain=DOMAIN, name='mummies r us', users=[user_id], case_sharing=True)
        group2.save()

        # first sync has both groups
        fixture = self.user.get_group_fixture(None)
        self.assertIsNotNone(fixture)
        check_xml_line_by_line(self, _get_group_fixture(user_id, [group1, group2]), ElementTree.tostring(fixture))

        # second sync is empty since nothing has changed
        last_sync_date = group1.last_modified + timedelta(seconds=1)
        fixture = self.user.get_group_fixture(FakeSyncLog(last_sync_date))
        self.assertIsNone(fixture)

        group2.remove_user(user_id)

        # third sync only has group1
        last_sync_date = group2.last_modified
        fixture = self.user.get_group_fixture(FakeSyncLog(last_sync_date))
        self.assertIsNotNone(fixture)
        check_xml_line_by_line(self, _get_group_fixture(user_id, [group1]), ElementTree.tostring(fixture))


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

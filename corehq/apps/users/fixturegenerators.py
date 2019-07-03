from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.xml import get_data_element


class UserGroupsFixtureProvider(FixtureProvider):
    """
    Generate user-based fixtures used in OTA restore
    """

    id = 'user-groups'

    def __call__(self, restore_state):
        """
        For a given user, return a fixture containing all the groups
        they are a part of.
        """
        fixture = self.get_group_fixture(restore_state.restore_user, restore_state.last_sync_log)
        if len(fixture):
            return [fixture]
        else:
            return []

    def get_group_fixture(self, restore_user, last_sync=None):
        # Always sync groups even though they have a last modified date since
        # we aren't keeping track of when users get removed from groups.
        # See https://github.com/dimagi/commcare-hq/pull/7148 for alternate approach
        groups = restore_user.get_case_sharing_groups()
        return self.group_fixture(groups, restore_user)

    def group_fixture(self, groups, restore_user):
        """
        <fixture id="user-groups" user_id="TXPLAKJDFLIKSDFLMSDLFKJ">
            <groups>
                <group id="IUOWERJLKSFDAMAJLK">
                    <name>Team Inferno</name>
                </group>
                <group id="OUPIZXCVHKAJSDFEWL">
                    <name>Team Disaster</name>
                    <group_data>
                        <data key="leader">colonel panic</data>
                        <data key="skills">hatin</data>
                    </group_data>
                </group>
            </groups>
        </fixture>
        """
        xFixture = ElementTree.Element('fixture', {'id': self.id, 'user_id': restore_user.user_id})
        xGroups = ElementTree.SubElement(xFixture, 'groups')

        for group in groups:
            xGroup = ElementTree.SubElement(xGroups, 'group', {'id': group.get_id})
            xName = ElementTree.SubElement(xGroup, 'name')
            xName.text = group.name
            if group.metadata:
                xGroup.append(get_data_element('group_data', group.metadata))

        return xFixture


user_groups = UserGroupsFixtureProvider()

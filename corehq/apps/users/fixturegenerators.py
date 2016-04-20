from __future__ import absolute_import
from xml.etree import ElementTree
from casexml.apps.phone.xml import get_data_element


class UserGroupsFixtureProvider(object):
    """
    Generate user-based fixtures used in OTA restore
    """

    id = 'user-groups'

    def __call__(self, user, version, last_sync=None, app=None):
        """
        For a given user, return a fixture containing all the groups
        they are a part of.
        """
        fixture = self.get_group_fixture(user, last_sync)
        if len(fixture):
            return [fixture]
        else:
            return []

    def get_group_fixture(self, user, last_sync=None):
        # Always sync groups even though they have a last modified date since
        # we aren't keeping track of when users get removed from groups.
        # See https://github.com/dimagi/commcare-hq/pull/7148 for alternate approach
        groups = user.get_case_sharing_groups()
        return self.group_fixture(groups, user)

    def group_fixture(self, groups, user):
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
        xFixture = ElementTree.Element('fixture', attrib={'id': self.id, 'user_id': user.user_id})
        xGroups = ElementTree.SubElement(xFixture, 'groups')

        for group in groups:
            xGroup = ElementTree.SubElement(xGroups, 'group', attrib={'id': group.get_id})
            xName = ElementTree.SubElement(xGroup, 'name')
            xName.text = group.name
            if group.metadata:
                xGroup.append(get_data_element('group_data', group.metadata))

        return xFixture

user_groups = UserGroupsFixtureProvider()

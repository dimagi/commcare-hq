from __future__ import absolute_import
from xml.etree import ElementTree
from casexml.apps.phone.xml import get_data_element


class UserGroupsFixtureProvider(object):
    """
    Generate user-based fixtures used in OTA restore
    """

    id = 'user-groups'

    def __call__(self, user, version, last_sync=None):
        """
        For a given user, return a fixture containing all the groups
        they are a part of.
        """
        fixture = self.get_group_fixture(user, last_sync)
        if fixture:
            return [fixture]
        else:
            return []

    def get_group_fixture(self, user, last_sync=None):
        def _should_sync_groups(groups, last_sync):
            """
            Determine if we need to sync the groups fixture by checking
            the modified date on all groups compared to the
            last sync.
            """
            if not last_sync or not last_sync.date:
                return True

            for group in groups:
                if not group.last_modified or group.last_modified >= last_sync.date:
                    return True

            return False

        groups = user.get_case_sharing_groups()

        if _should_sync_groups(groups, last_sync):
            return self.group_fixture(groups, user)
        else:
            return None

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

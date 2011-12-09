from __future__ import absolute_import
from lxml.etree import Element, SubElement

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
# this should eventually be harmonized with the other responses, but 
# has been implemented quick and dirty
from casexml.apps.phone import xml as phone_xml 

def get_response(user):
    response = phone_xml.get_response_element("Thanks for registering! Your username is %s" % user.username)
    response.append(phone_xml.get_registration_element(user.to_casexml_user()))
    return phone_xml.tostring(response)


def group_fixture(groups, user):
    """
    <fixture id="user-groups" user_id="TXPLAKJDFLIKSDFLMSDLFKJ">
        <groups>
            <group id="IUOWERJLKSFDAMAJLK">
                <name>Team Inferno</name>
            </group>
            <group id="OUPIZXCVHKAJSDFEWL">
                <name>Team Disaster</name>
            </group>
        </groups>
    </fixture>
    """

    xFixture = Element('fixture', attrib={'id': 'user-groups', 'user_id': user.user_id})
    xGroups = SubElement(xFixture, 'groups')

    for group in groups:
        xGroup = SubElement(xGroups, 'group', attrib={'id': group.get_id})
        xName = SubElement(xGroup, 'name')
        xName.text = group.name

    return xFixture
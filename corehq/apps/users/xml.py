from __future__ import absolute_import
from xml.etree import ElementTree

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
# this should eventually be harmonized with the other responses, but 
# has been implemented quick and dirty
from casexml.apps.phone import xml as phone_xml 
from receiver import xml as receiver_xml 
from receiver.xml import ResponseNature

def get_response(user, created):
    if created:   text = "Thanks for registering! Your username is %s" % user.username
    else:         text = "Thanks for updating your information, %s." % user.username
        
    nature = ResponseNature.SUBMIT_USER_REGISTERED if created else \
             ResponseNature.SUBMIT_USER_UPDATED
    response = receiver_xml.get_response_element(text, nature=nature)
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
    xFixture = ElementTree.Element('fixture', attrib={'id': 'user-groups', 'user_id': user.user_id})
    xGroups = ElementTree.SubElement(xFixture, 'groups')

    for group in groups:
        xGroup = ElementTree.SubElement(xGroups, 'group', attrib={'id': group.get_id})
        xName = ElementTree.SubElement(xGroup, 'name')
        xName.text = group.name

    return xFixture
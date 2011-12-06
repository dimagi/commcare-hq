from __future__ import absolute_import

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
    
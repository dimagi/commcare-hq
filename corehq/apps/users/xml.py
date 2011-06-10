

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
# this should eventually be harmonized with the other responses, but 
# has been implemented quick and dirty
from casexml.apps.phone.xml import get_response as phone_get_response
from casexml.apps.phone.xml import get_registration_xml


def get_response(user):
    reg_xml = get_registration_xml(user.to_casexml_user())
    return phone_get_response("Thanks for registering! Your username is %s" % user.username, reg_xml)
    
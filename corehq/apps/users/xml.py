

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
# this should eventually be harmonized with the other responses, but 
# has been implemented quick and dirty
from corehq.apps.users.util import raw_username
REGISTRATION_TEMPLATE = \
'''
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>%(username)s</username>
        <uuid>%(uuid)s</uuid>
    <Registration >'''

def get_response(user):
    from corehq.apps.phone.xml import get_response as phone_get_response
    reg_xml = REGISTRATION_TEMPLATE % \
        {"username": raw_username(user.username),
         "uuid": user._id }  
    return phone_get_response("Thanks for registering! Your username is %s" % user.username, reg_xml)
    
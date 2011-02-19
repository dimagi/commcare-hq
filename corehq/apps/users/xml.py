

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
# this should eventually be harmonized with the other responses, but 
# has been implemented quick and dirty
from corehq.apps.users.util import raw_username
REGISTRATION_TEMPLATE = \
"""
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>%(username)s</username>
        <password>%(password)s</password>
        <uuid>%(uuid)s</uuid>
        <date>%(date)s</date>%(user_data)s
    </Registration>"""

USER_DATA_TEMPLATE = \
"""
        <user_data>
            %(data)s
        </user_data>"""

def get_registration_xml(couch_user):
    cc_account = couch_user.default_commcare_account
    if not cc_account:
        raise Exception("can't restore a user without a commcare account!")
    
    # TODO: this doesn't feel like a final way to do this
    # all dates should be formatted like YYYY-MM-DD (e.g. 2010-07-28)
    return REGISTRATION_TEMPLATE % {"username":  raw_username(couch_user.username),
                                    "password":  cc_account.login.password,
                                    "uuid":      cc_account.login_id,
                                    "date":      cc_account.login.date_joined.strftime("%Y-%m-%d"),
                                    "user_data": get_user_data_xml(cc_account.user_data)
                                    }
def get_user_data_xml(dict):
    if not dict:  return ""
    return USER_DATA_TEMPLATE % \
        {"data": "\n            ".join('<data key="%(key)s">%(value)s</data>' % \
                                       {"key": key, "value": val } for key, val in dict.items())}    


def get_response(user):
    from corehq.apps.phone.xml import get_response as phone_get_response
    reg_xml = get_registration_xml(user)
    return phone_get_response("Thanks for registering! Your username is %s" % user.username, reg_xml)
    
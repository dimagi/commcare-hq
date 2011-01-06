

"""
This module is used to generate xml responses for user registrations.
Spec: https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI
"""
RESPONSE_TEMPLATE = \
'''<registration-response xmlns="openrosa.org/user-registration-response">
    <response-message>%(message)s</response_message>
</registration-response>'''

def get_response(user):
    # todo
    return RESPONSE_TEMPLATE % \
        {"message": "Thanks for registering! Your username is %s" % user.username}  
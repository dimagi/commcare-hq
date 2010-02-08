import logging


# some constants used by the submission handler
REGISTRATION_HANDLER = "registration_response"
APP_NAME = "hq"

# xmlns that registrations come in as. 
REGISTRATION_XMLNS = "openrosa.org/user-registration"

def create_phone_user(attachment):
    """Create a phone user from a file and attachment"""
    # this comes in as xml that looks like:
    # <n0:registration xmlns:n0="openrosa.org/user-registration">
    # <username>user</username>
    # <password>pw</password>
    # <uuid>MTBZJTDO3SCT2ONXAQ88WM0CH</uuid>
    # <date>2008-01-07</date>
    # <registering_phone_id>NRPHIOUSVEA215AJL8FFKGTVR</registering_phone_id>
    # <user_data> ... some custom stuff </user_data>
    
    # For now we will just save the user somewhere.
    # Where?
    
    # also tell the submission it was handled, so we can override the custom response
    # stupid dependencies
    from receiver.models import SubmissionHandlingType
    handle_type = SubmissionHandlingType.objects.get_or_create(app=APP_NAME, 
                                                               method=REGISTRATION_HANDLER)[0]
    attachment.submission.handled(handle_type)


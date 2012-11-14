from corehq.apps.sms import api
from corehq.apps.sms import util
from corehq.apps.sms.mixin import VerifiedNumber, CommCareMobileContactMixin
from corehq.apps.users.models import CommCareUser

OUTGOING = "Welcome to CommCareHQ! Is this phone used by %(name)s? If yes, reply '123' to enable SMS features for CommCareHQ on this phone."""
CONFIRM = "Thank you. This phone has been verified for using SMS with CommCareHQ"

def send_verification(domain, user, phone_number):
    message = OUTGOING % {'name': user.username.split('@')[0]}
    api.send_sms(domain, user._id, phone_number, message)

def process_verification(phone_number, text):
    v = VerifiedNumber.by_phone(phone_number, True)
    if not v:
        return

    if not verification_response_ok(text):
        return
    
    backend = util.get_outbound_sms_backend(phone_number, v.domain)

    # i don't know how to dynamically instantiate this object, which may be any number of doc types...
    #owner = CommCareMobileContactMixin.get(v.owner_id)
    assert v.owner_doc_type == 'CommCareUser'
    owner = CommCareUser.get(v.owner_id)

    owner.save_verified_number(v.domain, phone_number, True, backend._id)

    api.send_sms(v.domain, owner._id, phone_number, CONFIRM)

def verification_response_ok(text):
    return text == '123'

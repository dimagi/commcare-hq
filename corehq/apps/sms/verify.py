from django.utils.translation import ugettext as _, ugettext_noop
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.api import send_sms, send_sms_to_verified_number
from corehq.apps.sms.mixin import VerifiedNumber, MobileBackend
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms import util
from corehq.util.translation import localize

OUTGOING = ugettext_noop("Welcome to CommCareHQ! Is this phone used by %(name)s? If yes, reply '123'%(replyto)s to start using SMS with CommCareHQ.")
CONFIRM = ugettext_noop("Thank you. This phone has been verified for using SMS with CommCareHQ")

def send_verification(domain, user, phone_number):
    backend = MobileBackend.auto_load(phone_number, domain)
    reply_phone = backend.reply_to_phone_number

    with localize(user.language):
        message = _(OUTGOING) % {
            'name': user.username.split('@')[0],
            'replyto': ' to %s' % util.clean_phone_number(reply_phone) if reply_phone else '',
        }
        send_sms(domain, user, phone_number, message)

def process_verification(phone_number, msg, backend_id=None):
    v = VerifiedNumber.by_phone(phone_number, True)
    if not v:
        return

    if not verification_response_ok(msg.text):
        return

    msg.domain = v.domain
    msg.couch_recipient_doc_type = v.owner_doc_type
    msg.couch_recipient = v.owner_id
    msg.save()

    if not domain_has_privilege(msg.domain, privileges.INBOUND_SMS):
        return

    if backend_id:
        backend = MobileBackend.load(backend_id)
    else:
        backend = MobileBackend.auto_load(phone_number, v.domain)

    # i don't know how to dynamically instantiate this object, which may be any number of doc types...
    #owner = CommCareMobileContactMixin.get(v.owner_id)
    assert v.owner_doc_type == 'CommCareUser'
    owner = CommCareUser.get(v.owner_id)

    v = owner.save_verified_number(v.domain, phone_number, True, backend.name)
    with localize(owner.language):
        send_sms_to_verified_number(v, _(CONFIRM))

def verification_response_ok(text):
    return text == '123'

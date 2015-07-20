from dimagi.utils.couch import CriticalSection
from django.utils.translation import ugettext as _, ugettext_noop
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.api import (send_sms, send_sms_to_verified_number,
    MessageMetadata)
from corehq.apps.sms.mixin import VerifiedNumber, MobileBackend
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms import util
from corehq.apps.sms.models import MessagingEvent
from corehq.util.translation import localize

OUTGOING = ugettext_noop("Welcome to CommCareHQ! Is this phone used by %(name)s? If yes, reply '123'%(replyto)s to start using SMS with CommCareHQ.")
CONFIRM = ugettext_noop("Thank you. This phone has been verified for using SMS with CommCareHQ")

VERIFICATION__ALREADY_IN_USE = 1
VERIFICATION__ALREADY_VERIFIED = 2
VERIFICATION__RESENT_PENDING = 3
VERIFICATION__WORKFLOW_STARTED = 4


def initiate_sms_verification_workflow(contact, phone_number):
    # For now this is only applicable to mobile workers
    assert isinstance(contact, CommCareUser)

    logged_event = MessagingEvent.get_current_verification_event(
        contact.domain, contact.get_id, phone_number)

    with CriticalSection(['verifying-phone-number-%s' % phone_number]):
        vn = VerifiedNumber.by_phone(phone_number, include_pending=True)
        if vn:
            if vn.owner_id != contact._id:
                return VERIFICATION__ALREADY_IN_USE
            if vn.verified:
                return VERIFICATION__ALREADY_VERIFIED
            else:
                result = VERIFICATION__RESENT_PENDING
        else:
            contact.save_verified_number(contact.domain, phone_number, False)
            result = VERIFICATION__WORKFLOW_STARTED
            # Always create a new event when the workflow starts
            if logged_event:
                logged_event.status = MessagingEvent.STATUS_NOT_COMPLETED
                logged_event.save()
            logged_event = MessagingEvent.create_verification_event(contact.domain, contact)

        if not logged_event:
            logged_event = MessagingEvent.create_verification_event(contact.domain, contact)

        send_verification(contact.domain, contact, phone_number, logged_event)
        return result


def send_verification(domain, user, phone_number, logged_event):
    backend = MobileBackend.auto_load(phone_number, domain)
    reply_phone = backend.reply_to_phone_number

    subevent = logged_event.create_subevent_for_single_sms(
        user.doc_type,
        user.get_id
    )

    with localize(user.language):
        message = _(OUTGOING) % {
            'name': user.username.split('@')[0],
            'replyto': ' to %s' % util.clean_phone_number(reply_phone) if reply_phone else '',
        }
        send_sms(domain, user, phone_number, message,
            metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
        subevent.completed()


def process_verification(phone_number, msg, backend_id=None):
    v = VerifiedNumber.by_phone(phone_number, True)
    if not v:
        return

    logged_event = MessagingEvent.get_current_verification_event(
        v.domain, v.owner_id, phone_number)

    if not logged_event:
        logged_event = MessagingEvent.create_verification_event(v.domain, v.owner)

    subevent = logged_event.create_subevent_for_single_sms(
        v.owner_doc_type,
        v.owner_id
    )
    subevent.completed()

    msg.domain = v.domain
    msg.couch_recipient_doc_type = v.owner_doc_type
    msg.couch_recipient = v.owner_id
    msg.messaging_subevent_id = subevent.pk
    msg.save()

    if (
        not domain_has_privilege(msg.domain, privileges.INBOUND_SMS) or
        not verification_response_ok(msg.text)
    ):
        return

    if backend_id:
        backend = MobileBackend.load(backend_id)
    else:
        backend = MobileBackend.auto_load(phone_number, v.domain)

    assert v.owner_doc_type == 'CommCareUser'
    owner = CommCareUser.get(v.owner_id)

    v = owner.save_verified_number(v.domain, phone_number, True, backend.name)

    logged_event.completed()

    subevent = logged_event.create_subevent_for_single_sms(
        v.owner_doc_type,
        v.owner_id
    )

    with localize(owner.language):
        send_sms_to_verified_number(v, _(CONFIRM),
            metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
        subevent.completed()


def verification_response_ok(text):
    return text == '123'

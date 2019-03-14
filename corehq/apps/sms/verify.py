from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.couch import CriticalSection
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.api import (send_sms, send_sms_to_verified_number,
    MessageMetadata)
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms import messages
from corehq.apps.sms.mixin import apply_leniency, PhoneNumberInUseException
from corehq.apps.sms.models import MessagingEvent, SQLMobileBackend, PhoneNumber
from corehq.util.python_compatibility import soft_assert_type_text
import six

VERIFICATION__ALREADY_IN_USE = 1
VERIFICATION__ALREADY_VERIFIED = 2
VERIFICATION__RESENT_PENDING = 3
VERIFICATION__WORKFLOW_STARTED = 4


def initiate_sms_verification_workflow(contact, phone_number):
    # For now this is only applicable to mobile workers
    assert isinstance(contact, CommCareUser)

    phone_number = apply_leniency(phone_number)

    logged_event = MessagingEvent.get_current_verification_event(
        contact.domain, contact.get_id, phone_number)

    p = PhoneNumber.get_reserved_number(phone_number)
    if p:
        if p.owner_id != contact.get_id:
            return VERIFICATION__ALREADY_IN_USE
        if p.verified:
            return VERIFICATION__ALREADY_VERIFIED
        else:
            result = VERIFICATION__RESENT_PENDING
    else:
        entry = contact.get_or_create_phone_entry(phone_number)
        try:
            entry.set_pending_verification()
        except PhoneNumberInUseException:
            # On the off chance that the phone number was reserved between
            # the check above and now
            return VERIFICATION__ALREADY_IN_USE

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
    backend = SQLMobileBackend.load_default_by_phone_and_domain(
        SQLMobileBackend.SMS,
        phone_number,
        domain=domain
    )
    reply_phone = backend.reply_to_phone_number

    subevent = logged_event.create_subevent_for_single_sms(
        user.doc_type,
        user.get_id
    )

    if reply_phone:
        message = messages.get_message(
            messages.MSG_VERIFICATION_START_WITH_REPLY,
            context=(user.raw_username, reply_phone),
            domain=domain,
            language=user.get_language_code()
        )
    else:
        message = messages.get_message(
            messages.MSG_VERIFICATION_START_WITHOUT_REPLY,
            context=(user.raw_username,),
            domain=domain,
            language=user.get_language_code()
        )
    send_sms(domain, user, phone_number, message,
        metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
    subevent.completed()


def process_verification(v, msg, verification_keywords=None, create_subevent_for_inbound=True):
    verification_keywords = verification_keywords or ['123']

    logged_event = MessagingEvent.get_current_verification_event(
        v.domain, v.owner_id, v.phone_number)

    if not logged_event:
        logged_event = MessagingEvent.create_verification_event(v.domain, v.owner)

    msg.domain = v.domain
    msg.couch_recipient_doc_type = v.owner_doc_type
    msg.couch_recipient = v.owner_id

    if create_subevent_for_inbound:
        subevent = logged_event.create_subevent_for_single_sms(
            v.owner_doc_type,
            v.owner_id
        )
        subevent.completed()
        msg.messaging_subevent_id = subevent.pk

    msg.save()

    if (
        not domain_has_privilege(msg.domain, privileges.INBOUND_SMS) or
        not verification_response_ok(msg.text, verification_keywords)
    ):
        return False

    v.set_two_way()
    v.set_verified()
    v.save()

    logged_event.completed()
    subevent = logged_event.create_subevent_for_single_sms(
        v.owner_doc_type,
        v.owner_id
    )

    message = messages.get_message(
        messages.MSG_VERIFICATION_SUCCESSFUL,
        verified_number=v
    )
    send_sms_to_verified_number(v, message,
        metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
    subevent.completed()
    return True


def verification_response_ok(text, verification_keywords):
    if not isinstance(text, six.string_types):
        return False
    soft_assert_type_text(text)

    text = text.lower()
    return any([keyword in text for keyword in verification_keywords])

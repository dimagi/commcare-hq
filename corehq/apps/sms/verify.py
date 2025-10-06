import logging

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms import messages
from corehq.apps.sms.api import (
    MessageMetadata,
    send_sms,
    send_message_to_verified_number,
)
from corehq.apps.sms.mixin import PhoneNumberInUseException, apply_leniency
from corehq.apps.sms.models import (
    MessagingEvent,
    PhoneNumber,
    SQLMobileBackend,
)
from corehq.apps.users.models import CommCareUser

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
    logging.info(
        "Sending verification SMS: domain=%s, user_id=%s, phone_number=%s, username=%s",
        domain, user.get_id, phone_number, user.raw_username
    )

    backend = SQLMobileBackend.load_default_by_phone_and_domain(
        SQLMobileBackend.SMS,
        phone_number,
        domain=domain
    )
    reply_phone = backend.reply_to_phone_number
    logging.info("Loaded SMS backend: name=%s, reply_phone=%s", backend.name, reply_phone)

    subevent = logged_event.create_subevent_for_single_sms(
        user.doc_type,
        user.get_id
    )
    logging.info("Created verification subevent: id=%s", subevent.pk)

    if reply_phone:
        logging.info("Creating verification message with reply phone: %s", reply_phone)
        message = messages.get_message(
            messages.MSG_VERIFICATION_START_WITH_REPLY,
            context=(user.raw_username, reply_phone),
            domain=domain,
            language=user.get_language_code()
        )
    else:
        logging.info("Creating verification message without reply phone")
        message = messages.get_message(
            messages.MSG_VERIFICATION_START_WITHOUT_REPLY,
            context=(user.raw_username,),
            domain=domain,
            language=user.get_language_code()
        )

    logging.info("Sending verification SMS to phone_number=%s with message preview: %s",
                phone_number, message[:50] + "..." if len(message) > 50 else message)
    send_sms(domain, user, phone_number, message,
             metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
    subevent.completed()
    logging.info("Verification SMS sent successfully to phone_number=%s", phone_number)


def process_verification(verified_number, msg, verification_keywords=None, create_subevent_for_inbound=True):
    verification_keywords = verification_keywords or ['123']

    logging.info(
        "Processing verification response: phone_number=%s, domain=%s, owner_id=%s, text_preview=%s",
        verified_number.phone_number, verified_number.domain, verified_number.owner_id,
        msg.text[:20] + "..." if len(msg.text) > 20 else msg.text
    )
    logging.info("Verification keywords: %s", verification_keywords)

    logged_event = MessagingEvent.get_current_verification_event(
        verified_number.domain, verified_number.owner_id, verified_number.phone_number)

    if not logged_event:
        logging.info("No existing verification event found, creating new one")
        logged_event = MessagingEvent.create_verification_event(verified_number.domain, verified_number.owner)
    else:
        logging.info("Found existing verification event: id=%s", logged_event.pk)

    msg.domain = verified_number.domain
    msg.couch_recipient_doc_type = verified_number.owner_doc_type
    msg.couch_recipient = verified_number.owner_id
    logging.info("Updated message with verified number info: domain=%s, recipient=%s",
                 msg.domain, msg.couch_recipient)

    if create_subevent_for_inbound:
        subevent = logged_event.create_subevent_for_single_sms(
            verified_number.owner_doc_type,
            verified_number.owner_id
        )
        subevent.completed()
        msg.messaging_subevent_id = subevent.pk
        logging.info("Created inbound verification subevent: id=%s", subevent.pk)

    msg.save()

    # Check if verification should succeed
    has_privilege = domain_has_privilege(msg.domain, privileges.INBOUND_SMS)
    response_ok = verification_response_ok(msg.text, verification_keywords)

    logging.info("Verification checks: has_privilege=%s, response_ok=%s", has_privilege, response_ok)

    if not has_privilege or not response_ok:
        if not has_privilege:
            logging.info("Verification failed: domain %s does not have INBOUND_SMS privilege", msg.domain)
        if not response_ok:
            logging.info("Verification failed: response text '%s' does not match keywords %s",
                        msg.text, verification_keywords)
        return False

    logging.info("Verification successful for phone_number=%s, setting as verified and two-way",
                verified_number.phone_number)
    verified_number.set_two_way()
    verified_number.set_verified()
    verified_number.save()

    logged_event.completed()
    logging.info("Completed verification event: id=%s", logged_event.pk)

    subevent = logged_event.create_subevent_for_single_sms(
        verified_number.owner_doc_type,
        verified_number.owner_id
    )

    message = messages.get_message(
        messages.MSG_VERIFICATION_SUCCESSFUL,
        verified_number=verified_number
    )
    logging.info("Sending verification success message to phone_number=%s", verified_number.phone_number)
    send_message_to_verified_number(verified_number, message,
                                metadata=MessageMetadata(messaging_subevent_id=subevent.pk))
    subevent.completed()
    logging.info("Verification process completed successfully for phone_number=%s", verified_number.phone_number)
    return True


def verification_response_ok(text, verification_keywords):
    if not isinstance(text, str):
        return False

    text = text.lower()
    return any([keyword in text for keyword in verification_keywords])

import logging
import random
import string
from django.conf import settings
from django.core.exceptions import ValidationError
from corehq.apps.users.models import CommCareUser, CouchUser
from django.forms import forms
from corehq.apps.users.util import format_username

from dimagi.utils.modules import to_function
from dimagi.utils.logging import notify_exception
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.util import (clean_phone_number, clean_text,
    get_available_backends)
from corehq.apps.sms.models import (SMSLog, OUTGOING, INCOMING,
    PhoneNumber, ERROR_PHONE_NUMBER_OPTED_OUT)
from corehq.apps.sms.messages import (get_message, MSG_OPTED_IN,
    MSG_OPTED_OUT, MSG_DUPLICATE_USERNAME, MSG_USERNAME_TOO_LONG)
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber, SMSBackend
from corehq.apps.domain.models import Domain
from datetime import datetime

from corehq.apps.sms.util import register_sms_contact, strip_plus

# A list of all keywords which allow registration via sms.
# Meant to allow support for multiple languages.
# Keywords should be in all caps.
REGISTRATION_KEYWORDS = ["JOIN"]
REGISTRATION_MOBILE_WORKER_KEYWORDS = ["WORKER"]


class DomainScopeValidationError(Exception):
    pass


class BackendAuthorizationException(Exception):
    pass


class MessageMetadata(object):
    def __init__(self, *args, **kwargs):
        self.workflow = kwargs.get("workflow", None)
        self.xforms_session_couch_id = kwargs.get("xforms_session_couch_id", None)
        self.reminder_id = kwargs.get("reminder_id", None)
        self.chat_user_id = kwargs.get("chat_user_id", None)
        self.ignore_opt_out = kwargs.get("ignore_opt_out", False)


def add_msg_tags(msg, metadata):
    if msg and metadata:
        msg.workflow = metadata.workflow
        msg.xforms_session_couch_id = metadata.xforms_session_couch_id
        msg.reminder_id = metadata.reminder_id
        msg.chat_user_id = metadata.chat_user_id
        msg.ignore_opt_out = metadata.ignore_opt_out
        msg.save()


def log_sms_exception(msg):
    direction = "OUT" if msg.direction == OUTGOING else "IN"
    message = "[SMS %s] Error processing SMS" % direction
    notify_exception(None, message=message, details={
        'domain': msg.domain,
        'date': msg.date,
        'message_id': msg._id,
    })


def send_sms(domain, contact, phone_number, text, metadata=None):
    """
    Sends an outbound SMS. Returns false if it fails.
    """
    if phone_number is None:
        return False
    if isinstance(phone_number, int) or isinstance(phone_number, long):
        phone_number = str(phone_number)
    phone_number = clean_phone_number(phone_number)

    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date = datetime.utcnow(),
        backend_id=None,
        text = text
    )
    if contact:
        msg.couch_recipient = contact._id
        msg.couch_recipient_doc_type = contact.doc_type
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def send_sms_to_verified_number(verified_number, text, metadata=None):
    """
    Sends an sms using the given verified phone number entry.

    verified_number The VerifiedNumber entry to use when sending.
    text            The text of the message to send.

    return  True on success, False on failure
    """
    backend = verified_number.backend
    msg = SMSLog(
        couch_recipient_doc_type = verified_number.owner_doc_type,
        couch_recipient = verified_number.owner_id,
        phone_number = "+" + str(verified_number.phone_number),
        direction = OUTGOING,
        date = datetime.utcnow(),
        domain = verified_number.domain,
        backend_id = backend._id,
        text = text
    )
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def send_sms_with_backend(domain, phone_number, text, backend_id, metadata=None):
    phone_number = clean_phone_number(phone_number)
    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=datetime.utcnow(),
        backend_id=backend_id,
        text=text
    )
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def send_sms_with_backend_name(domain, phone_number, text, backend_name, metadata=None):
    phone_number = clean_phone_number(phone_number)
    backend = MobileBackend.load_by_name(domain, backend_name)
    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=datetime.utcnow(),
        backend_id=backend._id,
        text=text
    )
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def enqueue_directly(msg):
    try:
        from corehq.apps.sms.management.commands.run_sms_queue import SMSEnqueuingOperation
        SMSEnqueuingOperation().enqueue_directly(msg)
    except:
        # If this direct enqueue fails, no problem, it will get picked up
        # shortly.
        pass


def queue_outgoing_sms(msg):
    if settings.SMS_QUEUE_ENABLED:
        try:
            msg.processed = False
            msg.datetime_to_process = msg.date
            msg.queued_timestamp = datetime.utcnow()
            msg.save()
        except:
            log_sms_exception(msg)
            return False

        enqueue_directly(msg)
        return True
    else:
        msg.processed = True
        msg_sent = send_message_via_backend(msg)
        return msg_sent


def send_message_via_backend(msg, backend=None, orig_phone_number=None):
    """send sms using a specific backend

    msg - outbound message object
    backend - MobileBackend object to use for sending; if None, use
      msg.outbound_backend
    orig_phone_number - the originating phone number to use when sending; this
      is sent in if the backend supports load balancing
    """
    try:
        msg.text = clean_text(msg.text)
    except Exception:
        logging.exception("Could not clean text for sms dated '%s' in domain '%s'" % (msg.date, msg.domain))
    try:
        phone_obj = PhoneNumber.get_by_phone_number_or_none(msg.phone_number)
        if phone_obj and not phone_obj.send_sms:
            if msg.ignore_opt_out and phone_obj.can_opt_in:
                # If ignore_opt_out is True on the message, then we'll still
                # send it. However, if we're not letting the phone number
                # opt back in and it's in an opted-out state, we will not
                # send anything to it no matter the state of the ignore_opt_out
                # flag.
                pass
            else:
                msg.set_system_error(ERROR_PHONE_NUMBER_OPTED_OUT)
                return False

        if not backend:
            backend = msg.outbound_backend
            # note: this will handle "verified" contacts that are still pending
            # verification, thus the backend is None. it's best to only call
            # send_sms_to_verified_number on truly verified contacts, though

        if not msg.backend_id:
            msg.backend_id = backend._id

        if backend.domain_is_authorized(msg.domain):
            backend.send(msg, orig_phone_number=orig_phone_number)
        else:
            raise BackendAuthorizationException("Domain '%s' is not authorized to use backend '%s'" % (msg.domain, backend._id))

        try:
            msg.backend_api = backend.__class__.get_api_id()
        except Exception:
            pass
        msg.save()
        create_billable_for_sms(msg)
        return True
    except Exception:
        log_sms_exception(msg)
        return False


def random_password():
    """
    This method creates a random password for an sms user registered via sms
    """
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for x in range(15))


def process_username(username, domain):
    """
    Loosely based on code from apps/users/forms.py:255
    """
    from corehq.apps.users.forms import validate_username

    max_len_username = 80
    if len(username) > max_len_username:
        raise forms.ValidationError(get_message(msg_id=MSG_USERNAME_TOO_LONG, context=(username, max_len_username)))
    # Check if the username contains invalid characters w/ django checker
    validate_username('%s@commcarehq.org' % username)
    username = format_username(username, domain)
    num_couch_users = len(CouchUser.view("users/by_username",
                                         key=username,
                                         reduce=False))
    if num_couch_users > 0:
        raise forms.ValidationError(get_message(msg_id=MSG_DUPLICATE_USERNAME, context=username))

    return username


def process_sms_registration(msg):
    """
    This method handles registration via sms.
    Returns True if a contact was registered, False if not.

    To have a case register itself, do the following:

        1) Select "Enable Case Registration Via SMS" in project settings, and fill in the
        associated Case Registration settings.

        2) Text in "join <domain>", where <domain> is the domain to join. If the sending
        number does not exist in the system, a case will be registered tied to that number.
        The "join" keyword can be any keyword in REGISTRATION_KEYWORDS. This is meant to
        support multiple translations.

    To have a mobile worker register itself, do the following:

        1) Select "Enable Mobile Worker Registration via SMS" in project settings.

        2) Text in "join <domain> worker <username>", where <domain> is the domain to join and <username> is the
        requested username.  If the username doesn't exist it will be created, otherwise the registration will error.
        If the username argument is not specified, the username will be the mobile number

        The "join" and "worker" keywords can be any keyword in REGISTRATION_KEYWORDS and
        REGISTRATION_MOBILE_WORKER_KEYWORDS, respectively. This is meant to support multiple
        translations.
    """
    registration_processed = False
    text_words = msg.text.upper().split()
    keyword1 = text_words[0] if len(text_words) > 0 else ""
    keyword2 = text_words[1].lower() if len(text_words) > 1 else ""
    keyword3 = text_words[2] if len(text_words) > 2 else ""
    keyword4 = text_words[3] if len(text_words) > 3 else ""
    cleaned_phone_number = strip_plus(msg.phone_number)
    if keyword1 in REGISTRATION_KEYWORDS and keyword2 != "":
        domain = Domain.get_by_name(keyword2, strict=True)
        if domain is not None:
            if domain_has_privilege(domain, privileges.INBOUND_SMS):
                if keyword3 in REGISTRATION_MOBILE_WORKER_KEYWORDS and domain.sms_mobile_worker_registration_enabled:
                    if keyword4 != '':
                        username = keyword4
                    else:
                        username = cleaned_phone_number
                    try:
                        username = process_username(username, domain)
                        password = random_password()
                        new_user = CommCareUser.create(domain.name, username, password)
                        new_user.add_phone_number(cleaned_phone_number)
                        new_user.save_verified_number(domain.name, cleaned_phone_number, True, None)
                        new_user.save()
                        registration_processed = True
                    except ValidationError as e:
                        send_sms(domain.name, None, cleaned_phone_number, str(e))

                elif domain.sms_case_registration_enabled:
                    register_sms_contact(
                        domain=domain.name,
                        case_type=domain.sms_case_registration_type,
                        case_name="unknown",
                        user_id=domain.sms_case_registration_user_id,
                        contact_phone_number=strip_plus(msg.phone_number),
                        contact_phone_number_is_verified="1",
                        owner_id=domain.sms_case_registration_owner_id,
                    )
                    registration_processed = True
            msg.domain = domain.name
            msg.save()

    return registration_processed


def incoming(phone_number, text, backend_api, timestamp=None,
             domain_scope=None, backend_message_id=None, delay=True,
             backend_attributes=None, raw_text=None):
    """
    entry point for incoming sms

    phone_number - originating phone number
    text - message content
    backend_api - backend API ID of receiving sms backend
    timestamp - message received timestamp; defaults to now (UTC)
    domain_scope - if present, only messages from phone numbers that can be
      definitively linked to this domain will be processed; others will be
      dropped (useful to provide security when simulating incoming sms)
    """
    # Log message in message log
    if text is None:
        text = ""
    phone_number = clean_phone_number(phone_number)
    msg = SMSLog(
        phone_number = phone_number,
        direction = INCOMING,
        date = timestamp or datetime.utcnow(),
        text = text,
        domain_scope = domain_scope,
        backend_api = backend_api,
        backend_message_id = backend_message_id,
        raw_text=raw_text,
    )
    if backend_attributes:
        for k, v in backend_attributes.items():
            setattr(msg, k, v)
    if settings.SMS_QUEUE_ENABLED:
        msg.processed = False
        msg.datetime_to_process = datetime.utcnow()
        msg.queued_timestamp = msg.datetime_to_process
        msg.save()
        enqueue_directly(msg)
    else:
        msg.processed = True
        msg.save()
        process_incoming(msg, delay=delay)
    return msg


def is_opt_message(text, keyword_list):
    if not isinstance(text, basestring):
        return False

    text = text.strip().upper()
    return text in keyword_list


def get_opt_keywords(msg):
    backend_classes = get_available_backends(index_by_api_id=True)
    backend_class = backend_classes.get(msg.backend_api, SMSBackend)
    return (backend_class.get_opt_in_keywords(),
        backend_class.get_opt_out_keywords())


def process_incoming(msg, delay=True):
    v = VerifiedNumber.by_phone(msg.phone_number, include_pending=True)

    if v is not None and v.verified:
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
        msg.domain = v.domain
        msg.save()

    if msg.domain_scope:
        # only process messages for phones known to be associated with this domain
        if v is None or v.domain != msg.domain_scope:
            raise DomainScopeValidationError(
                'Attempted to simulate incoming sms from phone number not ' \
                'verified with this domain'
            )

    can_receive_sms = PhoneNumber.can_receive_sms(msg.phone_number)
    opt_in_keywords, opt_out_keywords = get_opt_keywords(msg)
    if is_opt_message(msg.text, opt_out_keywords) and can_receive_sms:
        if PhoneNumber.opt_out_sms(msg.phone_number):
            metadata = MessageMetadata(ignore_opt_out=True)
            text = get_message(MSG_OPTED_OUT, v, context=(opt_in_keywords[0],))
            if v:
                send_sms_to_verified_number(v, text, metadata=metadata)
            else:
                send_sms(msg.domain, None, msg.phone_number, text, metadata=metadata)
    elif is_opt_message(msg.text, opt_in_keywords) and not can_receive_sms:
        if PhoneNumber.opt_in_sms(msg.phone_number):
            text = get_message(MSG_OPTED_IN, v, context=(opt_out_keywords[0],))
            if v:
                send_sms_to_verified_number(v, text)
            else:
                send_sms(msg.domain, None, msg.phone_number, text)
    elif v is not None and v.verified:
        if domain_has_privilege(msg.domain, privileges.INBOUND_SMS):
            for h in settings.SMS_HANDLERS:
                try:
                    handler = to_function(h)
                except:
                    notify_exception(None, message=('error loading sms handler: %s' % h))
                    continue

                try:
                    was_handled = handler(v, msg.text, msg=msg)
                except Exception, e:
                    log_sms_exception(msg)
                    was_handled = False

                if was_handled:
                    break
    else:
        if not process_sms_registration(msg):
            import verify
            verify.process_verification(msg.phone_number, msg)

    if msg.domain and domain_has_privilege(msg.domain, privileges.INBOUND_SMS):
        create_billable_for_sms(msg)


def create_billable_for_sms(msg, delay=True):
    if not msg.domain:
        return
    try:
        from corehq.apps.sms.tasks import store_billable
        if delay:
            store_billable.delay(msg)
        else:
            store_billable(msg)
    except Exception as e:
        logging.error("[BILLING] Errors Creating SMS Billable: %s" % e)

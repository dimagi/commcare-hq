import logging
from django.conf import settings
from celery.task import task
import math

from dimagi.utils.modules import to_function
from dimagi.utils.logging import notify_exception
from corehq.apps.sms.util import clean_phone_number, format_message_list, clean_text
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING, ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD, WORKFLOW_KEYWORD
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.domain.models import Domain
from datetime import datetime

from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import _get_responses, start_session, \
    _responses_to_text
from corehq.apps.app_manager.models import Form
from corehq.apps.sms.util import register_sms_contact, strip_plus
from corehq.apps.reminders.util import create_immediate_reminder
from touchforms.formplayer.api import current_question
from dateutil.parser import parse
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.groups.models import Group

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

def add_msg_tags(msg, metadata):
    if msg and metadata:
        msg.workflow = metadata.workflow
        msg.xforms_session_couch_id = metadata.xforms_session_couch_id
        msg.reminder_id = metadata.reminder_id
        msg.chat_user_id = metadata.chat_user_id
        msg.save()

def log_sms_exception(msg):
    direction = "OUT" if msg.direction == OUTGOING else "IN"
    if msg._id:
        message = "[SMS %s] Error processing SMS %s" % (direction, msg._id)
    else:
        message = ("[SMS %s] Error processing SMS for domain %s on %s" %
            (direction, msg.domain, msg.date))
    notify_exception(None, message=message)


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

        NOTE: This is not yet implemented and may change slightly.

        1) Select "Enable Mobile Worker Registration via SMS" in project settings.

        2) Text in "join <domain> worker", where <domain> is the domain to join. If the
        sending number does not exist in the system, a PendingCommCareUser object will be
        created, tied to that number.
        The "join" and "worker" keywords can be any keyword in REGISTRATION_KEYWORDS and
        REGISTRATION_MOBILE_WORKER_KEYWORDS, respectively. This is meant to support multiple 
        translations.

        3) A domain admin will have to approve the addition of the mobile worker before
        a CommCareUser can actually be created.
    """
    registration_processed = False
    text_words = msg.text.upper().split()
    keyword1 = text_words[0] if len(text_words) > 0 else ""
    keyword2 = text_words[1].lower() if len(text_words) > 1 else ""
    keyword3 = text_words[2] if len(text_words) > 2 else ""
    if keyword1 in REGISTRATION_KEYWORDS and keyword2 != "":
        domain = Domain.get_by_name(keyword2, strict=True)
        if domain is not None:
            if keyword3 in REGISTRATION_MOBILE_WORKER_KEYWORDS and domain.sms_mobile_worker_registration_enabled:
                #TODO: Register a PendingMobileWorker object that must be approved by a domain admin
                pass
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
                msg.domain = domain.name
                msg.save()
                registration_processed = True
    
    return registration_processed

def incoming(phone_number, text, backend_api, timestamp=None, 
             domain_scope=None, backend_message_id=None, delay=True,
             backend_attributes=None):
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

    if v is not None and v.verified:
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

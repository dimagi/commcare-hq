import logging
import random
import string
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.logging import notify_error, notify_exception
from dimagi.utils.modules import to_function

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sms.messages import (
    MSG_DUPLICATE_USERNAME,
    MSG_OPTED_IN,
    MSG_OPTED_OUT,
    MSG_REGISTRATION_WELCOME_CASE,
    MSG_REGISTRATION_WELCOME_MOBILE_WORKER,
    MSG_USERNAME_TOO_LONG,
    get_message,
)
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    MessagingEvent,
    PhoneBlacklist,
    PhoneNumber,
    QueuedSMS,
    SQLMobileBackend,
    SQLSMSBackend,
)
from corehq.apps.sms.util import (
    clean_phone_number,
    clean_text,
    get_sms_backend_classes,
    is_contact_active,
    register_sms_contact,
    strip_plus,
)
from corehq.apps.smsbillables.utils import log_smsbillables_error
from corehq.apps.smsforms.models import (
    SMSChannel,
    XFormsSessionSynchronization,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.const import USER_CHANGE_VIA_SMS
from corehq.form_processor.utils import is_commcarecase
from corehq.util.metrics import metrics_counter
from corehq.util.metrics.load_counters import sms_load_counter
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse

# A list of all keywords which allow registration via sms.
# Meant to allow support for multiple languages.
# Keywords should be in all caps.
REGISTRATION_KEYWORDS = ["JOIN"]
REGISTRATION_MOBILE_WORKER_KEYWORDS = ["WORKER"]


class BackendAuthorizationException(Exception):
    pass


class DelayProcessing(Exception):
    pass


def get_utcnow():
    """
    Used to make it easier to mock utcnow() in the tests.
    """
    return datetime.utcnow()


class MessageMetadata(object):

    def __init__(self, *args, **kwargs):
        self.workflow = kwargs.get("workflow", None)
        self.xforms_session_couch_id = kwargs.get("xforms_session_couch_id", None)
        self.reminder_id = kwargs.get("reminder_id", None)
        self.chat_user_id = kwargs.get("chat_user_id", None)
        self.ignore_opt_out = kwargs.get("ignore_opt_out", None)
        self.location_id = kwargs.get('location_id', None)
        self.messaging_subevent_id = kwargs.get('messaging_subevent_id', None)
        self.custom_metadata = kwargs.get('custom_metadata', None)


def add_msg_tags(msg, metadata):
    if msg and metadata:
        fields = ('workflow', 'xforms_session_couch_id', 'reminder_id', 'chat_user_id',
                  'ignore_opt_out', 'location_id', 'messaging_subevent_id', 'custom_metadata')
        for field in fields:
            value = getattr(metadata, field)
            if value is not None:
                setattr(msg, field, value)


def log_sms_exception(msg):
    direction = "OUT" if msg.direction == OUTGOING else "IN"
    message = "[SMS %s] Error processing SMS" % direction
    notify_exception(None, message=message, details={
        'domain': msg.domain,
        'date': msg.date,
        'message_id': msg.couch_id,
    })


def get_location_id_by_contact(domain, contact):
    if isinstance(contact, CommCareUser):
        return contact.location_id
    elif isinstance(contact, WebUser):
        return contact.get_location_id(domain)
    else:
        return None


def get_location_id_by_verified_number(v):
    return get_location_id_by_contact(v.domain, v.owner)


def get_sms_class():
    return QueuedSMS if settings.SMS_QUEUE_ENABLED else SMS


def send_sms(domain, contact, phone_number, text, metadata=None, logged_subevent=None):
    """
    Sends an outbound SMS. Returns false if it fails.
    """
    if phone_number is None:
        return False
    if isinstance(phone_number, int):
        phone_number = str(phone_number)
    phone_number = clean_phone_number(phone_number)

    msg = get_sms_class()(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=get_utcnow(),
        backend_id=None,
        location_id=get_location_id_by_contact(domain, contact),
        text=text
    )
    if contact:
        msg.couch_recipient = contact.get_id
        msg.couch_recipient_doc_type = contact.doc_type

    if domain and contact and is_commcarecase(contact):
        backend_name = contact.get_case_property('contact_backend_id')
        backend_name = backend_name.strip() if isinstance(backend_name, str) else ''

        if backend_name:
            try:
                backend = SQLMobileBackend.load_by_name(SQLMobileBackend.SMS, domain, backend_name)
            except BadSMSConfigException as e:
                if logged_subevent:
                    logged_subevent.error(MessagingEvent.ERROR_GATEWAY_NOT_FOUND,
                        additional_error_text=str(e))
                return False

            msg.backend_id = backend.couch_id

    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def send_sms_to_verified_number(verified_number, text, metadata=None, logged_subevent=None, events=None):
    """
    Sends an sms using the given verified phone number entry.

    verified_number The PhoneNumber entry to use when sending.
    text            The text of the message to send.

    return  True on success, False on failure
    """
    try:
        backend = verified_number.backend
    except BadSMSConfigException as e:
        if logged_subevent:
            logged_subevent.error(MessagingEvent.ERROR_GATEWAY_NOT_FOUND,
                additional_error_text=str(e))
            return False
        raise

    msg = get_sms_class()(
        couch_recipient_doc_type=verified_number.owner_doc_type,
        couch_recipient=verified_number.owner_id,
        phone_number="+" + str(verified_number.phone_number),
        direction=OUTGOING,
        date=get_utcnow(),
        domain=verified_number.domain,
        backend_id=backend.couch_id,
        location_id=get_location_id_by_verified_number(verified_number),
        text=text
    )
    add_msg_tags(msg, metadata)

    msg.custom_metadata = {}
    events = [] if events is None else events
    for event in events:
        multimedia_fields = ('caption_image', 'caption_audio', 'caption_video')
        for field in multimedia_fields:
            value = getattr(event, field, None)
            if value is not None:
                msg.custom_metadata[field] = value
    msg.save()

    return queue_outgoing_sms(msg)


def send_sms_with_backend(domain, phone_number, text, backend_id, metadata=None):
    phone_number = clean_phone_number(phone_number)
    msg = get_sms_class()(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=get_utcnow(),
        backend_id=backend_id,
        text=text
    )
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def send_sms_with_backend_name(domain, phone_number, text, backend_name, metadata=None):
    phone_number = clean_phone_number(phone_number)
    backend = SQLMobileBackend.load_by_name(SQLMobileBackend.SMS, domain, backend_name)
    msg = get_sms_class()(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=get_utcnow(),
        backend_id=backend.couch_id,
        text=text
    )
    add_msg_tags(msg, metadata)

    return queue_outgoing_sms(msg)


def enqueue_directly(msg):
    try:
        from corehq.apps.sms.management.commands.run_sms_queue import SMSEnqueuingOperation
        SMSEnqueuingOperation().enqueue(msg)
    except:
        # If this direct enqueue fails, no problem, it will get picked up
        # shortly.
        pass


def queue_outgoing_sms(msg):
    if settings.SMS_QUEUE_ENABLED:
        try:
            msg.processed = False
            msg.datetime_to_process = msg.date
            msg.queued_timestamp = get_utcnow()
            msg.save()
        except:
            log_sms_exception(msg)
            return False

        enqueue_directly(msg)
        return True
    else:
        msg.processed = True
        msg_sent = send_message_via_backend(msg)
        msg.publish_change()
        msg.update_subevent_activity()
        if msg_sent:
            create_billable_for_sms(msg)
        return msg_sent


def send_message_via_backend(msg, backend=None, orig_phone_number=None):
    """send sms using a specific backend

    msg - outbound message object
    backend - backend to use for sending; if None, msg.outbound_backend is used
    orig_phone_number - the originating phone number to use when sending; this
      is sent in if the backend supports load balancing
    """
    sms_load_counter("outbound", msg.domain)()
    try:
        msg.text = clean_text(msg.text)
    except Exception:
        logging.exception("Could not clean text for sms dated '%s' in domain '%s'" % (msg.date, msg.domain))
    try:
        # We need to send SMS when msg.domain is None to support sending to
        # people who opt in without being tied to a domain
        if msg.domain and not domain_has_privilege(msg.domain, privileges.OUTBOUND_SMS):
            raise Exception(
                ("Domain '%s' does not have permission to send SMS."
                 "  Please investigate why this function was called.") % msg.domain
            )

        phone_obj = PhoneBlacklist.get_by_phone_number_or_none(msg.phone_number)
        if phone_obj and not phone_obj.send_sms:
            if msg.ignore_opt_out and phone_obj.can_opt_in:
                # If ignore_opt_out is True on the message, then we'll still
                # send it. However, if we're not letting the phone number
                # opt back in and it's in an opted-out state, we will not
                # send anything to it no matter the state of the ignore_opt_out
                # flag.
                pass
            else:
                msg.set_system_error(SMS.ERROR_PHONE_NUMBER_OPTED_OUT)
                return False

        if not backend:
            backend = msg.outbound_backend

        if backend.domain_is_authorized(msg.domain):
            backend.send(msg, orig_phone_number=orig_phone_number)
            metrics_counter("commcare.sms.outbound_message", tags={
                'domain': msg.domain,
                'status': 'ok',
                'backend': _get_backend_tag(backend),
            })
        else:
            raise BackendAuthorizationException(
                "Domain '%s' is not authorized to use backend '%s'" % (msg.domain, backend.pk)
            )

        msg.backend_api = backend.hq_api_id
        msg.backend_id = backend.couch_id
        msg.save()
        return True
    except Exception as e:
        metrics_counter("commcare.sms.outbound_message", tags={
            'domain': msg.domain,
            'status': 'error',
            'backend': _get_backend_tag(backend),
        })
        should_log_exception = True

        if backend:
            should_log_exception = should_log_exception_for_backend(backend, e)

        if should_log_exception:
            log_sms_exception(msg)

        return False


@quickcache(['backend_id'], skip_arg='backend')
def _get_backend_tag(backend=None, backend_id=None):
    assert not (backend_id and backend)
    if backend_id:
        try:
            backend = SQLMobileBackend.load(backend_id, is_couch_id=True)
        except Exception:
            backend = None

    if not backend:
        return 'unknown'
    elif backend.is_global:
        return backend.name
    else:
        return f'{backend.domain}/{backend.name}'


def should_log_exception_for_backend(backend, exception):
    """
    Only returns True if the exception hasn't been logged for the given backend
    in the last hour.
    """
    client = get_redis_client()
    key = f'exception-logged-for-backend-{backend.couch_id}-{hash(str(exception))}'

    if client.get(key):
        return False
    else:
        client.set(key, 1)
        client.expire(key, 60 * 60)
        return True


def register_sms_user(
    username, cleaned_phone_number, domain, send_welcome_sms=False, admin_alert_emails=None
):
    try:
        username = process_username(username, domain)
        password = random_password()
        new_user = CommCareUser.create(
            domain,
            username,
            password,
            created_by=None,
            created_via=USER_CHANGE_VIA_SMS,
        )
        new_user.add_phone_number(cleaned_phone_number)
        new_user.save()

        entry = new_user.get_or_create_phone_entry(cleaned_phone_number)
        entry.set_two_way()
        entry.set_verified()
        entry.save()

        if send_welcome_sms:
            send_sms(
                domain, None, cleaned_phone_number,
                get_message(MSG_REGISTRATION_WELCOME_MOBILE_WORKER, domain=domain)
            )
        if admin_alert_emails:
            send_admin_registration_alert(domain, admin_alert_emails, new_user)
    except ValidationError as e:
        send_sms(domain, None, cleaned_phone_number, e.messages[0])
        return False
    else:
        return True


def random_password():
    """
    This method creates a random password for an sms user registered via sms
    """
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for x in range(15))


def process_username(username, domain):
    from corehq.apps.users.forms import (clean_mobile_worker_username,
        get_mobile_worker_max_username_length)

    max_length = get_mobile_worker_max_username_length(domain)

    return clean_mobile_worker_username(
        domain,
        username,
        name_too_long_message=get_message(MSG_USERNAME_TOO_LONG, context=(username, max_length)),
        name_exists_message=get_message(MSG_DUPLICATE_USERNAME, context=(username,))
    )


def send_admin_registration_alert(domain, recipients, user):
    from corehq.apps.users.views.mobile.users import EditCommCareUserView
    subject = _("New user {username} registered for {domain} through SMS").format(
        username=user.username,
        domain=domain,
    )
    html_content = render_to_string('sms/email/new_sms_user.html', {
        "username": user.username,
        "domain": domain,
        "url": absolute_reverse(EditCommCareUserView.urlname, args=[domain, user.get_id])
    })
    send_html_email_async.delay(subject, recipients, html_content,
                                domain=domain, use_domain_gateway=True)


def is_registration_text(text):
    keywords = text.strip().upper().split()
    if len(keywords) == 0:
        return False

    return keywords[0] in REGISTRATION_KEYWORDS


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

        2) Text in "join <domain> worker <username>", where <domain> is the domain to join
        and <username> is the requested username. If the username doesn't exist it will be
        created, otherwise the registration will error. If the username argument is not specified,
        the username will be the mobile number

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
    if is_registration_text(msg.text) and keyword2 != "":
        domain_name = keyword2

        if any_migrations_in_progress(domain_name):
            raise DelayProcessing()

        domain_obj = Domain.get_by_name(domain_name, strict=True)

        if domain_obj is not None:
            if domain_has_privilege(domain_obj, privileges.INBOUND_SMS):
                if (
                        keyword3 in REGISTRATION_MOBILE_WORKER_KEYWORDS
                        and domain_obj.sms_mobile_worker_registration_enabled
                ):
                    username = cleaned_phone_number if keyword4 == '' else keyword4
                    registration_processed = register_sms_user(
                        username=username,
                        domain=domain_obj.name,
                        cleaned_phone_number=cleaned_phone_number,
                        send_welcome_sms=domain_obj.enable_registration_welcome_sms_for_mobile_worker,
                        admin_alert_emails=list(domain_obj.sms_worker_registration_alert_emails),
                    )
                elif domain_obj.sms_case_registration_enabled:
                    register_sms_contact(
                        domain=domain_obj.name,
                        case_type=domain_obj.sms_case_registration_type,
                        case_name="unknown",
                        user_id=domain_obj.sms_case_registration_user_id,
                        contact_phone_number=cleaned_phone_number,
                        contact_phone_number_is_verified="1",
                        owner_id=domain_obj.sms_case_registration_owner_id,
                    )
                    registration_processed = True
                    if domain_obj.enable_registration_welcome_sms_for_case:
                        send_sms(domain_obj.name, None, cleaned_phone_number,
                                 get_message(MSG_REGISTRATION_WELCOME_CASE, domain=domain_obj.name))
            msg.domain = domain_obj.name
            msg.save()

    return registration_processed


def incoming(phone_number, text, backend_api, timestamp=None,
             domain_scope=None, backend_message_id=None,
             raw_text=None, backend_id=None, media_urls=None):
    """
    entry point for incoming sms

    phone_number - originating phone number
    text - message content
    backend_api - backend API ID of receiving sms backend
    timestamp - message received timestamp; defaults to now (UTC)
    domain_scope - set the domain scope for this SMS; see SMSBase.domain_scope for details
    media_urls - list of urls for media download.
    """
    # Log message in message log
    if text is None:
        text = ""
    phone_number = clean_phone_number(phone_number)
    msg = get_sms_class()(
        phone_number=phone_number,
        direction=INCOMING,
        date=timestamp or get_utcnow(),
        text=text,
        domain_scope=domain_scope,
        backend_api=backend_api,
        backend_id=backend_id,
        backend_message_id=backend_message_id,
        raw_text=raw_text,
    )
    if media_urls:
        msg.custom_metadata = {"media_urls": media_urls}

    if settings.SMS_QUEUE_ENABLED:
        msg.processed = False
        msg.datetime_to_process = get_utcnow()
        msg.queued_timestamp = msg.datetime_to_process
        msg.save()
        enqueue_directly(msg)
    else:
        msg.processed = True
        msg.save()
        process_incoming(msg)
    return msg


def is_opt_message(text, keyword_list):
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    if not isinstance(text, str):
        return False

    text = text.strip().upper()
    return text in keyword_list


def get_opt_keywords(msg):
    backend_class = get_sms_backend_classes().get(msg.backend_api, SQLSMSBackend)
    try:
        backend_model = msg.outbound_backend
    except (BadSMSConfigException, SQLMobileBackend.DoesNotExist):
        # Backend not found, we will just use the default
        custom_opt_out = []
        custom_opt_in = []
    else:
        custom_opt_out = backend_model.opt_out_keywords
        custom_opt_in = backend_model.opt_in_keywords
    return (
        backend_class.get_opt_in_keywords() + custom_opt_in,
        backend_class.get_opt_out_keywords() + custom_opt_out,
        backend_class.get_pass_through_opt_in_keywords(),
    )


def load_and_call(sms_handler_names, phone_number, text, sms):
    handled = False

    for sms_handler_name in sms_handler_names:
        try:
            handler = to_function(sms_handler_name)
        except:
            notify_exception(None, message=('error loading sms handler: %s' % sms_handler_name))
            continue

        try:
            handled = handler(phone_number, text, sms)
        except Exception:
            log_sms_exception(sms)

        if handled:
            break

    return handled


def get_inbound_phone_entry_from_sms(msg):
    return get_inbound_phone_entry(msg.phone_number, msg.backend_id)


def get_inbound_phone_entry(phone_number, backend_id=None):
    if backend_id:
        backend = SQLMobileBackend.load(backend_id, is_couch_id=True)
        if toggles.INBOUND_SMS_LENIENCY.enabled(backend.domain):
            p = None
            if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(backend.domain):
                running_session_info = XFormsSessionSynchronization.get_running_session_info_for_channel(
                    SMSChannel(backend_id=backend_id, phone_number=phone_number)
                )
                contact_id = running_session_info.contact_id
                if contact_id:
                    p = PhoneNumber.get_phone_number_for_owner(contact_id, phone_number)
                if p is not None:
                    return (
                        p,
                        True
                    )
                elif running_session_info.session_id:
                    # This would be very unusual, as it would mean the supposedly running form session
                    # is linked to a phone number, contact pair that doesn't exist in the PhoneNumber table
                    notify_error(
                        "Contact from running session has no match in PhoneNumber table. "
                        "Only known way for this to happen is if you "
                        "unregister a phone number for a contact "
                        "while they are in an active session.",
                        details={
                            'running_session_info': running_session_info
                        }
                    )

            # NOTE: I don't think the backend could ever be global here since global backends
            # don't have a 'domain' and so the toggles would never be activated
            if not backend.is_global:
                p = PhoneNumber.get_two_way_number_with_domain_scope(phone_number, backend.domains_with_access)
                return (
                    p,
                    p is not None
                )

    return (
        PhoneNumber.get_reserved_number(phone_number),
        False
    )


def process_incoming(msg):
    try:
        _process_incoming(msg)
        status = 'ok'
    except Exception:
        status = 'error'
        raise
    finally:
        # this needs to be in a try finally so we can
        # - get msg.domain after it's set
        # - report whether it raised an exception as status
        # - always report the metric even if it fails
        metrics_counter("commcare.sms.inbound_message", tags={
            'domain': msg.domain,
            'backend': _get_backend_tag(backend_id=msg.backend_id),
            'status': status,
        })


def _allow_load_handlers(verified_number, is_two_way, has_domain_two_way_scope):
    return (
        (is_two_way or has_domain_two_way_scope)
        and is_contact_active(verified_number.domain, verified_number.owner_doc_type, verified_number.owner_id)
    )


def _domain_accepts_inbound(msg):
    return msg.domain and domain_has_privilege(msg.domain, privileges.INBOUND_SMS)


def _process_incoming(msg):
    sms_load_counter("inbound", msg.domain)()
    verified_number, has_domain_two_way_scope = get_inbound_phone_entry_from_sms(msg)
    is_two_way = verified_number is not None and verified_number.is_two_way

    if verified_number:
        if any_migrations_in_progress(verified_number.domain):
            raise DelayProcessing()

        msg.couch_recipient_doc_type = verified_number.owner_doc_type
        msg.couch_recipient = verified_number.owner_id
        msg.domain = verified_number.domain
        msg.location_id = get_location_id_by_verified_number(verified_number)
        msg.save()

    elif msg.domain_scope:
        if any_migrations_in_progress(msg.domain_scope):
            raise DelayProcessing()

        msg.domain = msg.domain_scope
        msg.save()

    opt_in_keywords, opt_out_keywords, pass_through_opt_in_keywords = get_opt_keywords(msg)
    domain = verified_number.domain if verified_number else None
    opt_keyword = False

    if is_opt_message(msg.text, opt_out_keywords):
        if PhoneBlacklist.opt_out_sms(msg.phone_number, domain=domain):
            metadata = MessageMetadata(ignore_opt_out=True)
            text = get_message(MSG_OPTED_OUT, verified_number, context=(opt_in_keywords[0],))
            if verified_number:
                send_sms_to_verified_number(verified_number, text, metadata=metadata)
            elif msg.backend_id:
                send_sms_with_backend(msg.domain, msg.phone_number, text, msg.backend_id, metadata=metadata)
            else:
                send_sms(msg.domain, None, msg.phone_number, text, metadata=metadata)
            opt_keyword = True
    elif is_opt_message(msg.text, opt_in_keywords):
        if PhoneBlacklist.opt_in_sms(msg.phone_number, domain=domain):
            text = get_message(MSG_OPTED_IN, verified_number, context=(opt_out_keywords[0],))
            if verified_number:
                send_sms_to_verified_number(verified_number, text)
            elif msg.backend_id:
                send_sms_with_backend(msg.domain, msg.phone_number, text, msg.backend_id)
            else:
                send_sms(msg.domain, None, msg.phone_number, text)
            opt_keyword = True
    else:
        if is_opt_message(msg.text, pass_through_opt_in_keywords):
            # Opt the phone number in, and then process the message normally
            PhoneBlacklist.opt_in_sms(msg.phone_number, domain=domain)

    handled = False

    if _domain_accepts_inbound(msg):
        if verified_number and verified_number.pending_verification:
            from . import verify
            handled = verify.process_verification(
                verified_number, msg, create_subevent_for_inbound=not has_domain_two_way_scope)

        if _allow_load_handlers(verified_number, is_two_way, has_domain_two_way_scope):
            handled = load_and_call(settings.SMS_HANDLERS, verified_number, msg.text, msg)

    if not handled and not is_two_way and not opt_keyword:
        handled = process_sms_registration(msg)

    # If the sms queue is enabled, then the billable gets created in remove_from_queue()
    if (
        not settings.SMS_QUEUE_ENABLED
        and msg.domain
        and domain_has_privilege(msg.domain, privileges.INBOUND_SMS)
    ):
        create_billable_for_sms(msg)


def create_billable_for_sms(msg, delay=True):
    if not isinstance(msg, SMS):
        raise Exception("Expected msg to be an SMS")

    if settings.ENTERPRISE_MODE or not msg.domain:
        return

    try:
        from corehq.apps.sms.tasks import store_billable
        if delay:
            store_billable.delay(msg.couch_id)
        else:
            store_billable(msg.couch_id)
    except Exception as e:
        log_smsbillables_error("Errors Creating SMS Billable: %s" % e)

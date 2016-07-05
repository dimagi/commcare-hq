import math
from datetime import datetime, timedelta
from celery.task import task
from corehq.apps.sms.mixin import (InvalidFormatException,
    PhoneNumberInUseException)
from corehq.apps.sms.models import (OUTGOING, INCOMING, SMS,
    PhoneLoadBalancingMixin, QueuedSMS, PhoneNumber)
from corehq.apps.sms.api import (send_message_via_backend, process_incoming,
    log_sms_exception, create_billable_for_sms, get_utcnow)
from django.db import transaction
from django.conf import settings
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.smsbillables.exceptions import RetryBillableTaskException
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.sms.change_publishers import publish_sms_saved
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch import release_lock, CriticalSection
from dimagi.utils.rate_limit import rate_limit


def remove_from_queue(queued_sms):
    with transaction.atomic():
        sms = SMS()
        for field in sms._meta.fields:
            if field.name != 'id':
                setattr(sms, field.name, getattr(queued_sms, field.name))
        queued_sms.delete()
        sms.save()

    sms.publish_change()

    if sms.direction == OUTGOING and sms.processed and not sms.error:
        create_billable_for_sms(sms)
    elif sms.direction == INCOMING and sms.domain and domain_has_privilege(sms.domain, privileges.INBOUND_SMS):
        create_billable_for_sms(sms)


def handle_unsuccessful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    if msg.num_processing_attempts < settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS:
        delay_processing(msg, settings.SMS_QUEUE_REPROCESS_INTERVAL)
    else:
        msg.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
        remove_from_queue(msg)


def handle_successful_processing_attempt(msg):
    utcnow = get_utcnow()
    msg.num_processing_attempts += 1
    msg.processed = True
    msg.processed_timestamp = utcnow
    if msg.direction == OUTGOING:
        msg.date = utcnow
    msg.save()
    remove_from_queue(msg)


def delay_processing(msg, minutes):
    msg.datetime_to_process += timedelta(minutes=minutes)
    msg.save()


def get_lock(client, key):
    return client.lock(key, timeout=settings.SMS_QUEUE_PROCESSING_LOCK_TIMEOUT*60)


def time_within_windows(domain_now, windows):
    weekday = domain_now.weekday()
    time = domain_now.time()

    for window in windows:
        if (window.day in [weekday, -1] and
            (window.start_time is None or time >= window.start_time) and
            (window.end_time is None or time <= window.end_time)):
            return True

    return False


def handle_domain_specific_delays(msg, domain_object, utcnow):
    """
    Checks whether or not we need to hold off on sending an outbound message
    due to any restrictions set on the domain, and delays processing of the
    message if necessary.

    Returns True if a delay was made, False if not.
    """
    domain_now = ServerTime(utcnow).user_time(domain_object.get_default_timezone()).done()

    if len(domain_object.restricted_sms_times) > 0:
        if not time_within_windows(domain_now, domain_object.restricted_sms_times):
            delay_processing(msg, settings.SMS_QUEUE_DOMAIN_RESTRICTED_RETRY_INTERVAL)
            return True

    if msg.chat_user_id is None and len(domain_object.sms_conversation_times) > 0:
        if time_within_windows(domain_now, domain_object.sms_conversation_times):
            sms_conversation_length = domain_object.sms_conversation_length
            conversation_start_timestamp = utcnow - timedelta(minutes=sms_conversation_length)
            if SMS.inbound_entry_exists(
                msg.couch_recipient_doc_type,
                msg.couch_recipient,
                conversation_start_timestamp,
                to_timestamp=utcnow
            ):
                delay_processing(msg, 1)
                return True

    return False


def message_is_stale(msg, utcnow):
    oldest_allowable_datetime = \
        utcnow - timedelta(hours=settings.SMS_QUEUE_STALE_MESSAGE_DURATION)
    if isinstance(msg.date, datetime):
        return msg.date < oldest_allowable_datetime
    else:
        return True


def handle_outgoing(msg):
    """
    Should return a requeue flag, so if it returns True, the message will be
    requeued and processed again immediately, and if it returns False, it will
    not be queued again.
    """
    backend = msg.outbound_backend
    sms_rate_limit = backend.get_sms_rate_limit()
    use_rate_limit = sms_rate_limit is not None
    use_load_balancing = isinstance(backend, PhoneLoadBalancingMixin)
    orig_phone_number = None

    if use_load_balancing:
        orig_phone_number = backend.get_next_phone_number()

    if use_rate_limit:
        if use_load_balancing:
            redis_key = 'sms-rate-limit-backend-%s-phone-%s' % (backend.pk, orig_phone_number)
        else:
            redis_key = 'sms-rate-limit-backend-%s' % backend.pk

        if not rate_limit(redis_key, actions_allowed=sms_rate_limit, how_often=60):
            # Requeue the message and try it again shortly
            return True

    result = send_message_via_backend(
        msg,
        backend=backend,
        orig_phone_number=orig_phone_number
    )

    if msg.error:
        remove_from_queue(msg)
    else:
        # Only do the following if an unrecoverable error did not happen
        if result:
            handle_successful_processing_attempt(msg)
        else:
            handle_unsuccessful_processing_attempt(msg)

    return False


def handle_incoming(msg):
    try:
        process_incoming(msg)
        handle_successful_processing_attempt(msg)
    except:
        log_sms_exception(msg)
        handle_unsuccessful_processing_attempt(msg)


@task(queue="sms_queue", ignore_result=True, acks_late=True)
def process_sms(queued_sms_pk):
    """
    queued_sms_pk - pk of a QueuedSMS entry
    """
    client = get_redis_client()
    utcnow = get_utcnow()
    # Prevent more than one task from processing this SMS, just in case
    # the message got enqueued twice.
    message_lock = get_lock(client, "sms-queue-processing-%s" % queued_sms_pk)

    if message_lock.acquire(blocking=False):
        try:
            msg = QueuedSMS.objects.get(pk=queued_sms_pk)
        except QueuedSMS.DoesNotExist:
            # The message was already processed and removed from the queue
            release_lock(message_lock, True)
            return

        if message_is_stale(msg, utcnow):
            msg.set_system_error(SMS.ERROR_MESSAGE_IS_STALE)
            remove_from_queue(msg)
            release_lock(message_lock, True)
            return

        if msg.direction == OUTGOING:
            if msg.domain:
                domain_object = Domain.get_by_name(msg.domain)
            else:
                domain_object = None
            if domain_object and handle_domain_specific_delays(msg, domain_object, utcnow):
                release_lock(message_lock, True)
                return

        requeue = False
        # Process inbound SMS from a single contact one at a time
        recipient_block = msg.direction == INCOMING
        if (isinstance(msg.processed, bool)
            and not msg.processed
            and not msg.error
            and msg.datetime_to_process < utcnow):
            if recipient_block:
                recipient_lock = get_lock(client, 
                    "sms-queue-recipient-phone-%s" % msg.phone_number)
                recipient_lock.acquire(blocking=True)

            if msg.direction == OUTGOING:
                requeue = handle_outgoing(msg)
            elif msg.direction == INCOMING:
                handle_incoming(msg)
            else:
                msg.set_system_error(SMS.ERROR_INVALID_DIRECTION)
                remove_from_queue(msg)

            if recipient_block:
                release_lock(recipient_lock, True)

        release_lock(message_lock, True)
        if requeue:
            process_sms.delay(queued_sms_pk)


@task(ignore_result=True, default_retry_delay=5 * 60, max_retries=10, bind=True)
def store_billable(self, msg):
    if not isinstance(msg, SMS):
        raise Exception("Expected msg to be an SMS")

    if msg.couch_id and not SmsBillable.objects.filter(log_id=msg.couch_id).exists():
        try:
            msg.text.encode('iso-8859-1')
            msg_length = 160
        except UnicodeEncodeError:
            # This string contains unicode characters, so the allowed
            # per-sms message length is shortened
            msg_length = 70
        try:
            SmsBillable.create(
                msg,
                multipart_count=int(math.ceil(float(len(msg.text)) / msg_length)),
            )
        except RetryBillableTaskException as e:
            self.retry(exc=e)


@task(queue='background_queue', ignore_result=True, acks_late=True)
def delete_phone_numbers_for_owners(owner_ids):
    for p in PhoneNumber.objects.filter(owner_id__in=owner_ids):
        # Clear cache and delete
        p.delete()


@task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, ignore_result=True, acks_late=True,
      default_retry_delay=5 * 60, max_retries=10, bind=True)
def sync_case_phone_number(self, case):
    try:
        _sync_case_phone_number(case)
    except Exception as e:
        self.retry(exc=e)


def _phone_number_is_same(phone_number, phone_info):
    return (
        phone_number.phone_number == phone_info.phone_number and
        phone_number.backend_id == phone_info.sms_backend_id and
        phone_number.ivr_backend_id == phone_info.ivr_backend_id and
        phone_number.verified
    )


def _sync_case_phone_number(contact_case):
    phone_info = contact_case.get_phone_info()

    lock_keys = ['sync-case-phone-number-for-%s' % contact_case.case_id]
    if phone_info.phone_number:
        lock_keys.append('verifying-phone-number-%s' % phone_info.phone_number)

    with CriticalSection(lock_keys, timeout=5 * 60):
        phone_number = contact_case.get_verified_number()
        if (
            phone_number and
            phone_number.contact_last_modified and
            phone_number.contact_last_modified >= contact_case.server_modified_on
        ):
            return
        if phone_info.requires_entry:
            try:
                contact_case.verify_unique_number(phone_info.phone_number)
            except (InvalidFormatException, PhoneNumberInUseException):
                if phone_number:
                    phone_number.delete()
                return

            if not phone_number:
                phone_number = PhoneNumber(
                    domain=contact_case.domain,
                    owner_doc_type=contact_case.doc_type,
                    owner_id=contact_case.case_id,
                )
            elif _phone_number_is_same(phone_number, phone_info):
                return

            phone_number.phone_number = phone_info.phone_number
            phone_number.backend_id = phone_info.sms_backend_id
            phone_number.ivr_backend_id = phone_info.ivr_backend_id
            phone_number.verified = True
            phone_number.contact_last_modified = contact_case.server_modified_on
            phone_number.save()
        else:
            if phone_number:
                phone_number.delete()


@task(queue='background_queue', ignore_result=True, acks_late=True,
      default_retry_delay=5 * 60, max_retries=10, bind=True)
def publish_sms_change(self, sms):
    try:
        publish_sms_saved(sms)
    except Exception as e:
        self.retry(exc=e)

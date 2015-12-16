import math
from datetime import datetime, timedelta
from celery.task import task
from time import sleep
from corehq.apps.sms.mixin import SMSLoadBalancingMixin, VerifiedNumber
from corehq.apps.sms.models import (SMSLog, OUTGOING, INCOMING, SMS)
from corehq.apps.sms.api import (send_message_via_backend, process_incoming,
    log_sms_exception)
from django.conf import settings
from corehq.apps.domain.models import Domain
from corehq.apps.smsbillables.models import SmsBillable
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import soft_delete_docs
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch import release_lock
from threading import Thread


def handle_unsuccessful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    if msg.num_processing_attempts < settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS:
        delay_processing(msg, settings.SMS_QUEUE_REPROCESS_INTERVAL)
    else:
        msg.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)

def handle_successful_processing_attempt(msg):
    utcnow = datetime.utcnow()
    msg.num_processing_attempts += 1
    msg.processed = True
    msg.processed_timestamp = utcnow
    if msg.direction == OUTGOING:
        msg.date = utcnow
    msg.save()

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
            if SMSLog.inbound_entry_exists(msg.couch_recipient_doc_type,
                                           msg.couch_recipient,
                                           conversation_start_timestamp,
                                           utcnow):
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

def _wait_and_release_lock(lock, timeout, start_timestamp):
    while (datetime.utcnow() - start_timestamp) < timedelta(seconds=timeout):
        sleep(0.1)
    release_lock(lock, True)


def wait_and_release_lock(lock, timeout):
    timestamp = datetime.utcnow()
    t = Thread(target=_wait_and_release_lock, args=(lock, timeout, timestamp))
    t.start()

def handle_outgoing(msg):
    """
    Should return a requeue flag, so if it returns True, the message will be
    requeued and processed again immediately, and if it returns False, it will
    not be queued again.
    """
    backend = msg.outbound_backend
    sms_interval = backend.get_sms_interval()
    use_rate_limit = sms_interval is not None
    use_load_balancing = (isinstance(backend, SMSLoadBalancingMixin) and
        len(backend.phone_numbers) > 1)

    if use_rate_limit or use_load_balancing:
        client = get_redis_client()

    lbi = None
    orig_phone_number = None
    if use_load_balancing:
        lbi = backend.get_next_phone_number(client)
        orig_phone_number = lbi.phone_number
    elif (isinstance(backend, SMSLoadBalancingMixin) and 
        len(backend.phone_numbers) == 1):
        # If there's only one phone number, we don't need to go through the
        # load balancing algorithm. But we should always pass an
        # orig_phone_number if it's an instance of SMSLoadBalancingMixin.
        orig_phone_number = backend.phone_numbers[0]

    if use_rate_limit:
        if use_load_balancing:
            lock_key = "sms-backend-%s-rate-limit-phone-%s" % (backend._id,
                lbi.phone_number)
        else:
            lock_key = "sms-backend-%s-rate-limit" % backend._id
        lock = client.lock(lock_key, timeout=30)

    if not use_rate_limit or (use_rate_limit and lock.acquire(blocking=False)):
        if use_load_balancing:
            lbi.finish(save_stats=True)
        result = send_message_via_backend(msg, backend=backend, 
            orig_phone_number=orig_phone_number)
        if use_rate_limit:
            wait_and_release_lock(lock, sms_interval)

        # Only do the following if an unrecoverable error did not happen
        if not msg.error:
            if result:
                handle_successful_processing_attempt(msg)
            else:
                handle_unsuccessful_processing_attempt(msg)
        return False
    else:
        # We're using rate limiting, but couldn't acquire the lock, so
        # another thread is sending sms with this backend. Rather than wait,
        # we'll just put this message at the back of the queue.
        if use_load_balancing:
            lbi.finish(save_stats=False)
        return True

def handle_incoming(msg):
    try:
        process_incoming(msg)
        handle_successful_processing_attempt(msg)
    except:
        log_sms_exception(msg)
        handle_unsuccessful_processing_attempt(msg)


@task(queue="sms_queue", ignore_result=True, acks_late=True)
def process_sms(message_id):
    """
    message_id - _id of an SMSLog entry
    """
    client = get_redis_client()
    utcnow = datetime.utcnow()
    # Prevent more than one task from processing this SMS, just in case
    # the message got enqueued twice.
    message_lock = get_lock(client, "sms-queue-processing-%s" % message_id)

    if message_lock.acquire(blocking=False):
        msg = SMSLog.get(message_id)

        if message_is_stale(msg, utcnow):
            msg.set_system_error(SMS.ERROR_MESSAGE_IS_STALE)
            release_lock(message_lock, True)
            return

        if msg.direction == OUTGOING:
            if msg.domain:
                domain_object = Domain.get_by_name(msg.domain, strict=True)
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

            if recipient_block:
                release_lock(recipient_lock, True)

        release_lock(message_lock, True)
        if requeue:
            process_sms.delay(message_id)


@task(ignore_result=True)
def store_billable(msg):
    if msg._id and not SmsBillable.objects.filter(log_id=msg._id).exists():
        try:
            msg.text.encode('iso-8859-1')
            msg_length = 160
        except UnicodeEncodeError:
            # This string contains unicode characters, so the allowed
            # per-sms message length is shortened
            msg_length = 70
        for _ in range(int(math.ceil(float(len(msg.text)) / msg_length))):
            SmsBillable.create(msg)


@task(queue='background_queue', ignore_result=True, acks_late=True)
def delete_phone_numbers_for_owners(owner_ids):
    for ids in chunked(owner_ids, 50):
        results = VerifiedNumber.get_db().view(
            'sms/verified_number_by_owner_id',
            keys=ids,
            include_docs=True
        )
        soft_delete_docs([row['doc'] for row in results], VerifiedNumber)

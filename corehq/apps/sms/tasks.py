import pytz
import logging
from datetime import datetime, timedelta
from celery.task import task
from time import sleep
from redis_cache.cache import RedisCache
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.api import send_message_via_backend, process_incoming
from django.conf import settings
from corehq.apps.domain.models import Domain
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.couch.cache import cache_core

ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS = "TOO_MANY_UNSUCCESSFUL_ATTEMPTS"
ERROR_MESSAGE_IS_STALE = "MESSAGE_IS_STALE"
ERROR_INVALID_DIRECTION = "INVALID_DIRECTION"

def set_error(msg, system_error_message=None):
    msg.error = True
    msg.system_error_message = system_error_message
    msg.save()

def handle_unsuccessful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    if msg.num_processing_attempts < settings.SMS_QUEUE_MAX_PROCESSING_ATTEMPTS:
        delay_processing(msg, settings.SMS_QUEUE_REPROCESS_INTERVAL)
    else:
        set_error(msg, ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)

def handle_successful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    msg.processed = True
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
    domain_now = tz_utils.adjust_datetime_to_timezone(utcnow, pytz.utc.zone,
        domain_object.default_timezone)

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

def handle_outgoing(msg):
    def onerror():
        logging.exception("Exception while processing SMS %s" % msg._id)
    if send_message_via_backend(msg, onerror=onerror):
        handle_successful_processing_attempt(msg)
    else:
        handle_unsuccessful_processing_attempt(msg)

def handle_incoming(msg):
    try:
        process_incoming(msg)
        handle_successful_processing_attempt(msg)
    except:
        logging.exception("Exception while processing SMS %s" % msg._id)
        handle_unsuccessful_processing_attempt(msg)

@task(queue="sms_queue")
def process_sms(message_id):
    """
    message_id - _id of an SMSLog entry
    """
    # Note that Redis error/exception notifications go out from the
    # run_sms_queue command, so no need to send them out here
    # otherwise we'd get too many emails.
    rcache = cache_core.get_redis_default_cache()
    if not isinstance(rcache, RedisCache):
        return
    try:
        client = rcache.raw_client
    except NotImplementedError:
        return

    utcnow = datetime.utcnow()
    # Prevent more than one task from processing this SMS, just in case
    # the message got enqueued twice.
    message_lock = get_lock(client, "sms-queue-processing-%s" % message_id)

    if message_lock.acquire(blocking=False):
        msg = SMSLog.get(message_id)

        if message_is_stale(msg, utcnow):
            set_error(msg, ERROR_MESSAGE_IS_STALE)
            message_lock.release()
            return

        if msg.direction == OUTGOING:
            domain_object = Domain.get_by_name(msg.domain, strict=True)
            if handle_domain_specific_delays(msg, domain_object, utcnow):
                message_lock.release()
                return

        # Process inbound SMS from a single contact one at a time
        recipient_block = msg.direction == INCOMING
        if (isinstance(msg.processed, bool)
            and not msg.processed
            and not msg.error
            and msg.datetime_to_process < utcnow):
            if recipient_block:
                recipient_lock = get_lock(client, 
                    "sms-queue-recipient-%s" % msg.couch_recipient)
                recipient_lock.acquire(blocking=True)

            if msg.direction == OUTGOING:
                handle_outgoing(msg)
            elif msg.direction == INCOMING:
                handle_incoming(msg)
            else:
                set_error(msg, ERROR_INVALID_DIRECTION)

            if recipient_block:
                recipient_lock.release()
        message_lock.release()


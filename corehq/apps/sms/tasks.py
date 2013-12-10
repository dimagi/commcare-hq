from datetime import datetime, timedelta
from celery.task import task
from time import sleep
from redis_cache.cache import RedisCache
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.api import send_message_via_backend, process_incoming
from django.conf import settings

from dimagi.utils.couch.cache import cache_core
rcache = cache_core.get_redis_default_cache()

# 5-minute lock timeout
LOCK_TIMEOUT = 5

# 5-minute wait to reprocess an unsuccessful attempt
REPROCESS_INTERVAL = 5

# Max number of attempts before giving up on processing an SMS
MAX_PROCESSING_ATTEMPTS = 3

def handle_unsuccessful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    if msg.num_processing_attempts < MAX_PROCESSING_ATTEMPTS:
        msg.datetime_to_process += timedelta(minutes=REPROCESS_INTERVAL)    
        msg.save()
    else:
        msg.error = True
        msg.save()

def handle_successful_processing_attempt(msg):
    msg.num_processing_attempts += 1
    msg.processed = True
    msg.save()

@task(queue="sms_queue")
def process_sms(message_id):
    """
    message_id - _id of an SMSLog entry
    """
    if not isinstance(rcache, RedisCache):
        return
    try:
        client = rcache.raw_client
    except NotImplementedError:
        return

    message_key = "sms-queue-processing-%s" % message_id
    message_lock = client.lock(message_key, timeout=LOCK_TIMEOUT*60)
    utcnow = datetime.utcnow()

    if message_lock.acquire(blocking=False):
        msg = SMSLog.get(message_id)
        if not msg.processed and msg.datetime_to_process < utcnow:
            recipient_key = "sms-queue-recipient-%s" % msg.couch_recipient
            recipient_lock = client.lock(recipient_key, timeout=LOCK_TIMEOUT)
            recipient_lock.acquire(blocking=True)

            if msg.direction == OUTGOING:
                if send_message_via_backend(msg):
                    handle_successful_processing_attempt(msg)
                else:
                    handle_unsuccessful_processing_attempt(msg)
            elif msg.direction == INCOMING:
                try:
                    process_incoming(msg)
                    handle_successful_processing_attempt(msg)
                except:
                    handle_unsuccessful_processing_attempt(msg)
            else:
                handle_unsuccessful_processing_attempt(msg)

            recipient_lock.release()
    message_lock.release()


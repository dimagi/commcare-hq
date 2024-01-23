import hashlib
import math
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction

from celery.schedules import crontab

from corehq.util.metrics import metrics_gauge_task, metrics_counter
from corehq.util.metrics.const import MPM_MAX
from dimagi.utils.couch import (
    CriticalSection,
    get_redis_lock,
    release_lock,
)
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.rate_limit import rate_limit

from corehq import privileges
from corehq.apps.accounting.utils import (
    domain_has_privilege,
    domain_is_on_trial,
)
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import (
    DelayProcessing,
    create_billable_for_sms,
    get_utcnow,
    log_sms_exception,
    process_incoming,
    send_message_via_backend,
)
from corehq.apps.sms.change_publishers import publish_sms_saved
from corehq.apps.sms.mixin import (
    InvalidFormatException,
    PhoneNumberInUseException,
    apply_leniency,
)
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    DailyOutboundSMSLimitReached,
    PhoneLoadBalancingMixin,
    PhoneNumber,
    QueuedSMS,
)
from corehq.apps.sms.util import is_contact_active
from corehq.apps.smsbillables.exceptions import (
    RetryBillableTaskException,
)
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CouchUser
from corehq.util.celery_utils import no_result_task
from corehq.util.timezones.conversions import ServerTime

from corehq.apps.sms.const import DEFAULT_SMS_DAILY_LIMIT

MAX_TRIAL_SMS = 50


def remove_from_queue(queued_sms):
    with transaction.atomic():
        sms = get_sms_from_queued_sms(queued_sms)
        queued_sms.delete()
        sms.save()

    sms.publish_change()
    sms.update_subevent_activity()

    tags = {'backend': sms.backend_api}
    if sms.direction == OUTGOING and sms.processed and not sms.error:
        create_billable_for_sms(sms)
        metrics_counter('commcare.sms.outbound_succeeded', tags=tags)
    elif sms.direction == OUTGOING:
        metrics_counter('commcare.sms.outbound_failed', tags=tags)
    elif sms.direction == INCOMING and sms.domain and domain_has_privilege(sms.domain, privileges.INBOUND_SMS):
        create_billable_for_sms(sms)


def get_sms_from_queued_sms(queued_sms):
    sms = SMS()
    for field in _get_sms_fields_to_copy():
        setattr(sms, field, getattr(queued_sms, field))
    return sms


def _get_sms_fields_to_copy():
    """Returns a set of field attribute names to copy from QueuedSMS to SMS.
    This should be all fields in QueuedSMS except 'id'
    """
    res = set()
    for field in QueuedSMS._meta.get_fields():
        try:
            res.add(field.attname)  # use attname to avoid DB lookups for related models
        except AttributeError:
            res.add(field.name)
    return res - {"id"}


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


def get_lock(key):
    return get_redis_lock(
        key,
        timeout=settings.SMS_QUEUE_PROCESSING_LOCK_TIMEOUT * 60,
        name="_".join(key.split("-", 3)[:3]),
    )


def time_within_windows(domain_now, windows):
    weekday = domain_now.weekday()
    time = domain_now.time()

    for window in windows:
        if (
            window.day in [weekday, -1]
            and (window.start_time is None or time >= window.start_time)
            and (window.end_time is None or time <= window.end_time)
        ):
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


def get_connection_slot_from_phone_number(phone_number, max_simultaneous_connections):
    """
    Converts phone_number to a number between 0 and max_simultaneous_connections - 1.
    This is the connection slot number that will need be reserved in order to send
    the message.
    """
    hashed_phone_number = hashlib.sha1(phone_number.encode('utf-8')).hexdigest()
    return int(hashed_phone_number, base=16) % max_simultaneous_connections


def get_connection_slot_lock(phone_number, backend, max_simultaneous_connections):
    """
    There is one redis lock per connection slot, numbered from 0 to
    max_simultaneous_connections - 1.
    A slot is taken if the lock can't be acquired.
    """
    slot = get_connection_slot_from_phone_number(phone_number, max_simultaneous_connections)
    key = 'backend-%s-connection-slot-%s' % (backend.couch_id, slot)
    return get_redis_lock(key, timeout=60, name="connection_slot")


def passes_trial_check(msg):
    if msg.domain and domain_is_on_trial(msg.domain):
        with CriticalSection(['check-sms-sent-on-trial-for-%s' % msg.domain], timeout=60):
            key = 'sms-sent-on-trial-for-%s' % msg.domain
            expiry = 90 * 24 * 60 * 60
            client = get_redis_client()
            value = client.get(key) or 0
            if value >= MAX_TRIAL_SMS:
                msg.set_system_error(SMS.ERROR_TRIAL_SMS_EXCEEDED)
                return False

            client.set(key, value + 1, timeout=expiry)

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
    max_simultaneous_connections = backend.get_max_simultaneous_connections()
    orig_phone_number = None

    if use_load_balancing:
        orig_phone_number = backend.get_next_phone_number(msg.phone_number)

    if use_rate_limit:
        if use_load_balancing:
            redis_key = 'sms-rate-limit-backend-%s-phone-%s' % (backend.pk, orig_phone_number)
        else:
            redis_key = 'sms-rate-limit-backend-%s' % backend.pk

        if not rate_limit(redis_key, actions_allowed=sms_rate_limit, how_often=60):
            # Requeue the message and try it again shortly
            return True

    if max_simultaneous_connections:
        connection_slot_lock = get_connection_slot_lock(msg.phone_number, backend, max_simultaneous_connections)
        if not connection_slot_lock.acquire(blocking=False):
            # Requeue the message and try it again shortly
            return True

    if passes_trial_check(msg):
        result = send_message_via_backend(
            msg,
            backend=backend,
            orig_phone_number=orig_phone_number
        )

    if max_simultaneous_connections:
        release_lock(connection_slot_lock, True)

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
    except DelayProcessing:
        raise
    except Exception:
        log_sms_exception(msg)
        handle_unsuccessful_processing_attempt(msg)


class OutboundDailyCounter(object):

    def __init__(self, domain_object=None):
        self.domain_object = domain_object

        if domain_object:
            self.date = ServerTime(datetime.utcnow()).user_time(domain_object.get_default_timezone()).done().date()
        else:
            self.date = datetime.utcnow().date()

        self.key = 'outbound-daily-count-for-%s-%s' % (
            domain_object.name if domain_object else '',
            self.date.strftime('%Y-%m-%d')
        )

        # We need access to the raw redis client because calling incr on
        # a django_redis RedisCache object raises an error if the key
        # doesn't exist.
        self.client = get_redis_client().client.get_client()

    def increment(self):
        # If the key doesn't exist, redis will set it to 0 and then increment.
        value = self.client.incr(self.key)

        # If it's the first time we're calling incr, set the key's expiration
        if value == 1:
            self.client.expire(self.key, 24 * 60 * 60)

        return value

    def decrement(self):
        return self.client.decr(self.key)

    @property
    def current_usage(self):
        current_usage = self.client.get(self.key)
        if isinstance(current_usage, bytes):
            current_usage = int(current_usage.decode('utf-8'))
        return current_usage or 0

    @property
    def daily_limit(self):
        if self.domain_object:
            return self.domain_object.get_daily_outbound_sms_limit()
        else:
            # If the message isn't tied to a domain, still impose a limit.
            # Outbound messages not tied to a domain can happen when unregistered
            # contacts opt in or out from a gateway.
            return DEFAULT_SMS_DAILY_LIMIT

    def can_send_outbound_sms(self, queued_sms):
        """
        Returns False if the outbound daily limit has been exceeded.
        """
        value = self.increment()

        if value > self.daily_limit:
            # Delay processing by an hour so that in case the
            # limit gets increased within the same day, we start
            # processing the backlog right away.
            self.decrement()
            delay_processing(queued_sms, 60)
            domain = self.domain_object.name if self.domain_object else ''
            # Log the fact that we reached this limit and send alert on first breach
            # via Django Signals if needed
            DailyOutboundSMSLimitReached.create_for_domain_and_date(
                domain,
                self.date
            )
            return False

        return True


@no_result_task(queue="sms_queue", acks_late=True)
def process_sms(queued_sms_pk):
    """
    queued_sms_pk - pk of a QueuedSMS entry
    """
    utcnow = get_utcnow()
    # Prevent more than one task from processing this SMS, just in case
    # the message got enqueued twice.
    message_lock = get_lock("sms-queue-processing-%s" % queued_sms_pk)

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

        outbound_counter = None
        if msg.direction == OUTGOING:
            domain_object = Domain.get_by_name(msg.domain) if msg.domain else None

            if domain_object and handle_domain_specific_delays(msg, domain_object, utcnow):
                release_lock(message_lock, True)
                return

            outbound_counter = OutboundDailyCounter(domain_object)
            if not outbound_counter.can_send_outbound_sms(msg):
                release_lock(message_lock, True)
                return

        requeue = False
        # Process inbound SMS from a single contact one at a time
        recipient_block = msg.direction == INCOMING

        # We check datetime_to_process against utcnow plus a small amount
        # of time because timestamps can differ between machines which
        # can cause us to miss sending the message the first time and
        # result in an unnecessary delay.
        if (
            isinstance(msg.processed, bool)
            and not msg.processed
            and not msg.error
            and msg.datetime_to_process < (utcnow + timedelta(seconds=10))
        ):
            if recipient_block:
                recipient_lock = get_lock(
                    "sms-queue-recipient-phone-%s" % msg.phone_number)
                recipient_lock.acquire(blocking=True)

            if msg.direction == OUTGOING:
                if (
                    msg.domain
                    and msg.couch_recipient_doc_type
                    and msg.couch_recipient
                    and not is_contact_active(msg.domain, msg.couch_recipient_doc_type, msg.couch_recipient)
                ):
                    msg.set_system_error(SMS.ERROR_CONTACT_IS_INACTIVE)
                    remove_from_queue(msg)
                else:
                    requeue = handle_outgoing(msg)
            elif msg.direction == INCOMING:
                try:
                    handle_incoming(msg)
                except DelayProcessing:
                    process_sms.apply_async([queued_sms_pk], countdown=60)
                    if recipient_block:
                        release_lock(recipient_lock, True)
                    release_lock(message_lock, True)
            else:
                msg.set_system_error(SMS.ERROR_INVALID_DIRECTION)
                remove_from_queue(msg)

            if recipient_block:
                release_lock(recipient_lock, True)

        release_lock(message_lock, True)
        if requeue:
            if outbound_counter:
                outbound_counter.decrement()
            send_to_sms_queue(msg)


def send_to_sms_queue(queued_sms):
    process_sms.apply_async([queued_sms.pk])


@no_result_task(queue='background_queue', default_retry_delay=60 * 60,
                max_retries=23, bind=True)
def store_billable(self, msg_couch_id):
    """
    Creates billable in db that contains price of the message
    default_retry_delay/max_retries are set based on twilio support numbers:
    Most messages will have a price within 2 hours of delivery, all within 24 hours max
    """
    msg = SMS.objects.get(couch_id=msg_couch_id)
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
                multipart_count=int(math.ceil(len(msg.text) / msg_length)),
            )
        except RetryBillableTaskException as e:
            # WARNING: Please do not remove messages from this queue
            # unless you have a backup plan for how to process them
            # before the end of the month billing cycle. If not, LEAVE AS IS.
            self.retry(exc=e)


@no_result_task(queue='background_queue', acks_late=True)
def delete_phone_numbers_for_owners(owner_ids):
    for p in PhoneNumber.objects.filter(owner_id__in=owner_ids):
        # Clear cache and delete
        p.delete()


def clear_case_caches(case):
    from corehq.apps.sms.util import is_case_contact_active
    is_case_contact_active.clear(case.domain, case.case_id)


def sync_case_phone_number(contact_case):
    phone_info = contact_case.get_phone_info()

    with CriticalSection([contact_case.phone_sync_key], timeout=5 * 60):
        phone_numbers = contact_case.get_phone_entries()

        if len(phone_numbers) == 0:
            phone_number = None
        elif len(phone_numbers) == 1:
            phone_number = list(phone_numbers.values())[0]
        else:
            # We use locks to make sure this scenario doesn't happen, but if it
            # does, just clear the phone number entries and the right one will
            # be recreated below.
            for p in phone_numbers.values():
                p.delete()
            phone_number = None

        if (
            phone_number
            and phone_number.contact_last_modified
            and phone_number.contact_last_modified >= contact_case.server_modified_on
        ):
            return

        if not phone_info.requires_entry:
            if phone_number:
                phone_number.delete()
            return

        if phone_number and phone_number.phone_number != phone_info.phone_number:
            phone_number.delete()
            phone_number = None

        if not phone_number:
            phone_number = contact_case.create_phone_entry(phone_info.phone_number)

        phone_number.backend_id = phone_info.sms_backend_id
        phone_number.ivr_backend_id = phone_info.ivr_backend_id
        phone_number.contact_last_modified = contact_case.server_modified_on

        if phone_info.qualifies_as_two_way:
            try:
                phone_number.set_two_way()
                phone_number.set_verified()
            except PhoneNumberInUseException:
                pass
        else:
            phone_number.is_two_way = False
            phone_number.verified = False
            phone_number.pending_verification = False

        phone_number.save()


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=10, bind=True)
def sync_user_phone_numbers(self, couch_user_id):
    if not settings.USE_PHONE_ENTRIES:
        return

    try:
        _sync_user_phone_numbers(couch_user_id)
    except Exception as e:
        self.retry(exc=e)


def _sync_user_phone_numbers(couch_user_id):
    couch_user = CouchUser.get_by_user_id(couch_user_id)

    if not couch_user.is_commcare_user():
        # It isn't necessary to sync WebUser's phone numbers right now
        # and we need to think through how to support entries when a user
        # can belong to multiple domains
        return

    with CriticalSection([couch_user.phone_sync_key], timeout=5 * 60):
        phone_entries = couch_user.get_phone_entries()

        if couch_user.is_deleted() or not couch_user.is_active:
            for phone_number in phone_entries.values():
                phone_number.delete()
            return

        numbers_that_should_exist = [apply_leniency(phone_number) for phone_number in couch_user.phone_numbers]

        # Delete entries that should not exist
        for phone_number in phone_entries.keys():
            if phone_number not in numbers_that_should_exist:
                phone_entries[phone_number].delete()

        # Create entries that should exist but do not exist
        for phone_number in numbers_that_should_exist:
            if phone_number not in phone_entries:
                try:
                    couch_user.create_phone_entry(phone_number)
                except InvalidFormatException:
                    pass


@no_result_task(queue='background_queue', acks_late=True,
                default_retry_delay=5 * 60, max_retries=10, bind=True)
def publish_sms_change(self, sms_id):
    sms = SMS.objects.get(pk=sms_id)
    try:
        publish_sms_saved(sms)
    except Exception as e:
        self.retry(exc=e)


def queued_sms():
    return QueuedSMS.objects.count()


metrics_gauge_task('commcare.sms.queued', queued_sms, run_every=crontab(),
                   multiprocess_mode=MPM_MAX)

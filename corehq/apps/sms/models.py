#!/usr/bin/env python
import hashlib
from collections import namedtuple
from datetime import datetime

from django.contrib.postgres.fields import ArrayField
from django.db import IntegrityError, connection, models, transaction
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy, gettext_noop, gettext as _

import jsonfield

from dimagi.utils.couch import CriticalSection

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms import util as smsutil
from corehq.apps.sms.mixin import (
    BadSMSConfigException,
    PhoneNumberInUseException,
    apply_leniency,
)
from corehq.apps.users.models import CouchUser
from corehq.form_processor.models import CommCareCase
from corehq.util.mixin import UUIDGeneratorMixin
from corehq.util.quickcache import quickcache

INCOMING = "I"
OUTGOING = "O"

CALLBACK_PENDING = "PENDING"
CALLBACK_RECEIVED = "RECEIVED"
CALLBACK_MISSED = "MISSED"

WORKFLOW_CALLBACK = "CALLBACK"
WORKFLOW_REMINDER = "REMINDER"
WORKFLOW_KEYWORD = "KEYWORD"
WORKFLOW_FORWARD = "FORWARD"
WORKFLOW_BROADCAST = "BROADCAST"
WORKFLOW_DEFAULT = 'default'
WORKFLOWS_FOR_REPORTS = [
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    WORKFLOW_FORWARD,
    WORKFLOW_KEYWORD,
    WORKFLOW_REMINDER,
]

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))


class Log(models.Model):

    class Meta(object):
        abstract = True
        app_label = "sms"

    domain = models.CharField(max_length=126, null=True, db_index=True)
    date = models.DateTimeField(null=True, db_index=True)
    couch_recipient_doc_type = models.CharField(max_length=126, null=True, db_index=True)
    couch_recipient = models.CharField(max_length=126, null=True, db_index=True)
    phone_number = models.CharField(max_length=126, null=True, db_index=True)
    direction = models.CharField(max_length=1, null=True)
    error = models.BooleanField(null=True, default=False)
    system_error_message = models.TextField(null=True)
    system_phone_number = models.CharField(max_length=126, null=True)
    backend_api = models.CharField(max_length=126, null=True)
    backend_id = models.CharField(max_length=126, null=True)
    billed = models.BooleanField(null=True, default=False)

    # Describes what kind of workflow this log was a part of
    workflow = models.CharField(max_length=126, null=True)

    # If this log is related to a survey, this points to the couch_id
    # of an instance of SQLXFormsSession that this log is tied to
    xforms_session_couch_id = models.CharField(max_length=126, null=True, db_index=True)

    # If this log is related to a reminder, this points to the _id of a
    # CaseReminder instance that it is tied to
    reminder_id = models.CharField(max_length=126, null=True)
    location_id = models.CharField(max_length=126, null=True)

    # The MessagingSubEvent that this log is tied to
    messaging_subevent = models.ForeignKey('sms.MessagingSubEvent', null=True, on_delete=models.PROTECT)

    def set_gateway_error(self, message):
        """Set gateway error message or code

        :param message: Non-retryable message or code returned by the gateway.
        """
        self.set_system_error(f"Gateway error: {message}")

    def set_system_error(self, message=None):
        self.error = True
        self.system_error_message = message
        self.save()

    @classmethod
    def by_domain(cls, domain, start_date=None, end_date=None):
        qs = cls.objects.filter(domain=domain)

        if start_date:
            qs = qs.filter(date__gte=start_date)

        if end_date:
            qs = qs.filter(date__lte=end_date)

        return qs

    @classmethod
    def by_recipient(cls, contact_doc_type, contact_id):
        return cls.objects.filter(
            couch_recipient_doc_type=contact_doc_type,
            couch_recipient=contact_id,
        )

    @classmethod
    def get_last_log_for_recipient(cls, contact_doc_type, contact_id, direction=None):
        qs = cls.by_recipient(contact_doc_type, contact_id)

        if direction:
            qs = qs.filter(direction=direction)

        qs = qs.order_by('-date')[:1]

        if qs:
            return qs[0]

        return None

    @classmethod
    def count_by_domain(cls, domain, direction=None):
        qs = cls.objects.filter(domain=domain)

        if direction:
            qs = qs.filter(direction=direction)

        return qs.count()

    @property
    def recipient(self):
        if self.couch_recipient_doc_type == 'CommCareCase':
            return CommCareCase.objects.get_case(self.couch_recipient, self.domain)
        else:
            return CouchUser.get_by_user_id(self.couch_recipient)

    @classmethod
    def inbound_entry_exists(cls, contact_doc_type, contact_id, from_timestamp, to_timestamp=None):
        qs = cls.by_recipient(
            contact_doc_type,
            contact_id
        ).filter(
            direction=INCOMING,
            date__gte=from_timestamp
        )

        if to_timestamp:
            qs = qs.filter(
                date__lte=to_timestamp
            )

        return len(qs[:1]) > 0


class SMSBase(UUIDGeneratorMixin, Log):
    ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS = 'TOO_MANY_UNSUCCESSFUL_ATTEMPTS'
    ERROR_MESSAGE_IS_STALE = 'MESSAGE_IS_STALE'
    ERROR_INVALID_DIRECTION = 'INVALID_DIRECTION'
    ERROR_PHONE_NUMBER_OPTED_OUT = 'PHONE_NUMBER_OPTED_OUT'
    ERROR_INVALID_DESTINATION_NUMBER = 'INVALID_DESTINATION_NUMBER'
    ERROR_MESSAGE_TOO_LONG = 'MESSAGE_TOO_LONG'
    ERROR_CONTACT_IS_INACTIVE = 'CONTACT_IS_INACTIVE'
    ERROR_TRIAL_SMS_EXCEEDED = 'TRIAL_SMS_EXCEEDED'
    ERROR_MESSAGE_FORMAT_INVALID = 'MESSAGE_FORMAT_INVALID'
    ERROR_FAULTY_GATEWAY_CONFIGURATION = 'FAULTY_GATEWAY_CONFIGURATION'
    STATUS_PENDING = 'STATUS_PENDING'  # special value for pending status

    STATUS_SENT = "sent"
    STATUS_ERROR = "error"
    STATUS_QUEUED = "queued"
    STATUS_RECEIVED = "received"
    STATUS_FORWARDED = "forwarded"
    STATUS_DELIVERED = "delivered"  # the specific gateway need to tell us this
    STATUS_UNKNOWN = "unknown"

    STATUS_DISPLAY = {
        STATUS_SENT: _('Sent'),
        STATUS_DELIVERED: _('Delivered'),
        STATUS_ERROR: _('Error'),
        STATUS_QUEUED: _('Queued'),
        STATUS_RECEIVED: _('Received'),
        STATUS_FORWARDED: _('Forwarded'),
        STATUS_UNKNOWN: _('Unknown'),
    }

    DIRECTION_SLUGS = {
        INCOMING: "incoming",
        OUTGOING: "outgoing",
    }

    ERROR_MESSAGES = {
        ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS:
            gettext_noop('Gateway error.'),
        ERROR_MESSAGE_IS_STALE:
            gettext_noop('Message is stale and will not be processed.'),
        ERROR_INVALID_DIRECTION:
            gettext_noop('Unknown message direction.'),
        ERROR_PHONE_NUMBER_OPTED_OUT:
            gettext_noop('Phone number has opted out of receiving SMS.'),
        ERROR_INVALID_DESTINATION_NUMBER:
            gettext_noop("The gateway can't reach the destination number."),
        ERROR_MESSAGE_TOO_LONG:
            gettext_noop("The gateway could not process the message because it was too long."),
        'MESSAGE_BLANK':
            gettext_noop("The message was blank."),
        ERROR_CONTACT_IS_INACTIVE:
            gettext_noop("The recipient has been deactivated."),
        ERROR_TRIAL_SMS_EXCEEDED:
            gettext_noop("The number of SMS that can be sent on a trial plan has been exceeded."),
        ERROR_MESSAGE_FORMAT_INVALID:
            gettext_noop("The message format was invalid.")
    }

    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    text = models.TextField(null=True)

    # In cases where decoding must occur, this is the raw text received
    # from the gateway
    raw_text = models.TextField(null=True)
    datetime_to_process = models.DateTimeField(null=True, db_index=True)
    processed = models.BooleanField(null=True, default=True, db_index=True)
    num_processing_attempts = models.IntegerField(default=0, null=True)
    queued_timestamp = models.DateTimeField(null=True)
    processed_timestamp = models.DateTimeField(null=True)

    # When an SMS is received on a domain-owned backend, we set this to
    # the domain name. This can be used by the framework to handle domain-specific
    # processing of unregistered contacts.
    domain_scope = models.CharField(max_length=126, null=True)

    # Set to True to send the message regardless of whether the destination
    # phone number has opted-out. Should only be used to send opt-out
    # replies or other info-related queries while opted-out.
    ignore_opt_out = models.BooleanField(null=True, default=False)

    # This is the unique message id that the gateway uses to track this
    # message, if applicable.
    backend_message_id = models.CharField(max_length=126, null=True)

    # For outgoing sms only: if this sms was sent from a chat window,
    # the _id of the CouchUser who sent this sms; otherwise None
    chat_user_id = models.CharField(max_length=126, null=True)

    # True if this was an inbound message that was an
    # invalid response to a survey question
    invalid_survey_response = models.BooleanField(null=True, default=False)

    """ Custom properties. For the initial migration, it makes it easier
    to put these here. Eventually they should be moved to a separate table. """
    fri_message_bank_lookup_completed = models.BooleanField(null=True, default=False)
    fri_message_bank_message_id = models.CharField(max_length=126, null=True)
    fri_id = models.CharField(max_length=126, null=True)
    fri_risk_profile = models.CharField(max_length=1, null=True)

    # Holds any custom metadata for this SMS
    custom_metadata = jsonfield.JSONField(null=True, default=None)

    class Meta(object):
        abstract = True
        app_label = 'sms'

    @property
    def outbound_backend(self):
        if self.backend_id:
            return SQLMobileBackend.load(self.backend_id, is_couch_id=True)

        return SQLMobileBackend.load_default_by_phone_and_domain(
            SQLMobileBackend.SMS,
            smsutil.clean_phone_number(self.phone_number),
            domain=self.domain
        )

    def set_status_pending(self):
        """Mark message as sent with backend status pending"""
        self.error = False
        self.system_error_message = SMSBase.STATUS_PENDING
        self.save()

    def is_status_pending(self):
        return not self.error and self.system_error_message == SMSBase.STATUS_PENDING


class SMS(SMSBase):
    date_modified = models.DateTimeField(null=True, db_index=True, auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['processed_timestamp'])]

    def to_json(self):
        from corehq.apps.sms.serializers import SMSSerializer
        data = SMSSerializer(self).data
        return data

    def publish_change(self):
        from corehq.apps.sms.change_publishers import publish_sms_saved
        from corehq.apps.sms.tasks import publish_sms_change
        try:
            publish_sms_saved(self)
        except Exception:
            publish_sms_change.delay(self.id)

    def update_subevent_activity(self):
        subevent = self.messaging_subevent
        if subevent:
            subevent.update_date_last_activity()

    def requeue(self):
        if self.processed or self.direction != OUTGOING:
            raise ValueError("Should only requeue outgoing messages that haven't yet been proccessed")

        with transaction.atomic():
            queued_sms = QueuedSMS()
            for field in self._meta.fields:
                if field.name != 'id':
                    setattr(queued_sms, field.name, getattr(self, field.name))

            queued_sms.processed = False
            queued_sms.error = False
            queued_sms.system_error_message = None
            queued_sms.num_processing_attempts = 0
            queued_sms.date = datetime.utcnow()
            queued_sms.datetime_to_process = datetime.utcnow()
            queued_sms.queued_timestamp = datetime.utcnow()
            queued_sms.processed_timestamp = None
            self.delete()
            queued_sms.save()

    @staticmethod
    def get_counts_by_date(domain, start_date, end_date, time_zone):
        """
        Retrieves counts of SMS sent and received over the given date range
        for the given domain.

        :param domain: the domain
        :param start_date: the start date, as a date type
        :param end_date: the end date (inclusive), as a date type
        :param time_zone: the time zone to use when grouping counts by date,
        as a string type (e.g., 'America/New_York')

        :return: A list of (date, direction, count) named tuples
        """

        CountTuple = namedtuple('CountTuple', ['date', 'direction', 'sms_count'])

        query = """
        SELECT  (date AT TIME ZONE %s)::DATE AS date,
                direction,
                COUNT(*) AS sms_count
        FROM    sms_sms
        WHERE   domain = %s
        AND     date >= (%s + TIME '00:00') AT TIME ZONE %s
        AND     date < (%s + 1 + TIME '00:00') AT TIME ZONE %s
        AND     (direction = 'I' OR (direction = 'O' and processed))
        GROUP BY 1, 2
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [time_zone, domain, start_date, time_zone, end_date, time_zone]
            )
            return [CountTuple(*row) for row in cursor.fetchall()]


class QueuedSMS(SMSBase):

    class Meta(object):
        db_table = 'sms_queued'

    @classmethod
    def get_queued_sms(cls):
        return cls.objects.filter(
            datetime_to_process__lte=datetime.utcnow(),
        ).order_by('datetime_to_process')


class SQLLastReadMessage(UUIDGeneratorMixin, models.Model):

    class Meta(object):
        db_table = 'sms_lastreadmessage'
        app_label = 'sms'
        index_together = [
            ['domain', 'read_by', 'contact_id'],
            ['domain', 'contact_id'],
        ]

    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    domain = models.CharField(max_length=126, null=True)

    # _id of CouchUser who read it
    read_by = models.CharField(max_length=126, null=True)

    # _id of the CouchUser or CommCareCase who the message was sent to
    # or from
    contact_id = models.CharField(max_length=126, null=True)

    # couch_id of the SMS
    message_id = models.CharField(max_length=126, null=True)

    # date of the SMS entry, stored here redundantly to prevent a lookup
    message_timestamp = models.DateTimeField(null=True)

    @classmethod
    def by_anyone(cls, domain, contact_id):
        """
        Returns the SQLLastReadMessage representing the last chat message
        that was read by anyone in the given domain for the given contact_id.
        """
        result = cls.objects.filter(
            domain=domain,
            contact_id=contact_id
        ).order_by('-message_timestamp')
        result = result[:1]

        if len(result) > 0:
            return result[0]

        return None

    @classmethod
    def by_user(cls, domain, user_id, contact_id):
        """
        Returns the SQLLastReadMessage representing the last chat message
        that was read in the given domain by the given user_id for the given
        contact_id.
        """
        try:
            # It's not expected that this can raise MultipleObjectsReturned
            # since we lock out creation of these records with a CriticalSection.
            # So if that happens, let the exception raise.
            return cls.objects.get(
                domain=domain,
                read_by=user_id,
                contact_id=contact_id
            )
        except cls.DoesNotExist:
            return None


class ExpectedCallback(UUIDGeneratorMixin, models.Model):

    class Meta(object):
        app_label = 'sms'
        index_together = [
            ['domain', 'date'],
        ]

    STATUS_CHOICES = (
        (CALLBACK_PENDING, gettext_lazy("Pending")),
        (CALLBACK_RECEIVED, gettext_lazy("Received")),
        (CALLBACK_MISSED, gettext_lazy("Missed")),
    )

    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    domain = models.CharField(max_length=126, null=True, db_index=True)
    date = models.DateTimeField(null=True)
    couch_recipient_doc_type = models.CharField(max_length=126, null=True)
    couch_recipient = models.CharField(max_length=126, null=True, db_index=True)
    status = models.CharField(max_length=126, null=True)

    @classmethod
    def by_domain(cls, domain, start_date=None, end_date=None):
        qs = cls.objects.filter(domain=domain)

        if start_date:
            qs = qs.filter(date__gte=start_date)

        if end_date:
            qs = qs.filter(date__lte=end_date)

        return qs

    @classmethod
    def by_domain_recipient_date(cls, domain, recipient_id, date):
        try:
            return cls.objects.get(
                domain=domain,
                couch_recipient=recipient_id,
                date=date
            )
        except cls.DoesNotExist:
            return None


class PhoneBlacklist(models.Model):
    """
    Each entry represents a single phone number and whether we can send SMS
    to that number or make calls to that number.
    """

    # This is the domain that the phone number belonged to the last time an opt in
    # or opt out operation happened. Can be null if the phone number didn't belong
    # to any domain.
    domain = models.CharField(max_length=126, null=True, db_index=True)
    phone_number = models.CharField(max_length=30, unique=True, null=False, db_index=True)

    # True if it's ok to send SMS to this phone number, False if not
    send_sms = models.BooleanField(null=False, default=True)

    # True if it's ok to call this phone number, False if not
    # This is not yet implemented but will be in the future.
    send_ivr = models.BooleanField(null=False, default=True)

    # True to allow this phone number to opt back in, False if not
    can_opt_in = models.BooleanField(null=False, default=True)

    last_sms_opt_in_timestamp = models.DateTimeField(null=True)
    last_sms_opt_out_timestamp = models.DateTimeField(null=True)

    class Meta(object):
        app_label = 'sms'

    @classmethod
    def get_by_phone_number(cls, phone_number):
        phone_number = smsutil.strip_plus(phone_number)
        return cls.objects.get(phone_number=phone_number)

    @classmethod
    def get_by_phone_number_or_none(cls, phone_number):
        try:
            return cls.get_by_phone_number(phone_number)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_create(cls, phone_number):
        """
        phone_number - should be a string of digits
        """
        phone_number = smsutil.strip_plus(phone_number)
        if not phone_number:
            return (None, False)
        return cls.objects.get_or_create(phone_number=phone_number)

    @classmethod
    def can_receive_sms(cls, phone_number):
        try:
            phone_obj = cls.get_by_phone_number(phone_number)
            return phone_obj.send_sms
        except cls.DoesNotExist:
            # This means the phone number has not opted-out
            return True

    @classmethod
    def opt_in_sms(cls, phone_number, domain=None):
        """
        Opts a phone number in to receive SMS.
        Returns True if the number was actually opted-in, False if not.
        """
        phone_obj = cls.get_or_create(phone_number)[0]
        if not phone_obj.can_opt_in:
            return False

        phone_obj.domain = domain
        phone_obj.send_sms = True
        phone_obj.last_sms_opt_in_timestamp = datetime.utcnow()
        phone_obj.save()
        return True

    @classmethod
    def opt_out_sms(cls, phone_number, domain=None):
        """
        Opts a phone number out from receiving SMS.
        Does not bother changing the state for numbers marked as excluded from the opt in workflow.
        """
        phone_obj = cls.get_or_create(phone_number)[0]
        if not phone_obj.can_opt_in:
            return False

        phone_obj.domain = domain
        phone_obj.send_sms = False
        phone_obj.last_sms_opt_out_timestamp = datetime.utcnow()
        phone_obj.save()
        return True


class PhoneNumber(UUIDGeneratorMixin, models.Model):
    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, db_index=True, null=True)
    domain = models.CharField(max_length=126, db_index=True, null=True)
    owner_doc_type = models.CharField(max_length=126, null=True)
    owner_id = models.CharField(max_length=126, db_index=True, null=True)
    phone_number = models.CharField(max_length=126, db_index=True, null=True)

    # Points to the name of a SQLMobileBackend (can be domain-level
    # or system-level) which represents the backend that will be used
    # when sending SMS to this number. Can be None to use domain/system
    # defaults.
    backend_id = models.CharField(max_length=126, null=True)

    # Points to the name of a SQLMobileBackend (can be domain-level
    # or system-level) which represents the backend that will be used
    # when making calls to this number. Can be None to use domain/system
    # defaults.
    ivr_backend_id = models.CharField(max_length=126, null=True)
    verified = models.BooleanField(null=True, default=False)
    contact_last_modified = models.DateTimeField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    # If True, this phone number can be used for inbound SMS as well as outbound
    # (because when we look up the phone number for inbound SMS, we get this entry back).
    # If False, this phone number can only be used for outbound SMS because another
    # PhoneNumber entry is marked with is_two_way=True for the same phone_number.
    is_two_way = models.BooleanField()

    # True if the verification workflow has been started and not completed for this PhoneNumber
    pending_verification = models.BooleanField()

    def __init__(self, *args, **kwargs):
        super(PhoneNumber, self).__init__(*args, **kwargs)
        self._old_phone_number = self.phone_number
        self._old_owner_id = self.owner_id

    def __repr__(self):
        return '{phone} in {domain} (owned by {owner})'.format(
            phone=self.phone_number, domain=self.domain,
            owner=self.owner_id
        )

    @property
    def backend(self):
        from corehq.apps.sms.util import clean_phone_number
        backend_id = self.backend_id.strip() if isinstance(self.backend_id, str) else None
        if backend_id:
            return SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                self.domain,
                backend_id
            )
        else:
            return SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                clean_phone_number(self.phone_number),
                domain=self.domain
            )

    @property
    def owner(self):
        if self.owner_doc_type == 'CommCareCase':
            return CommCareCase.objects.get_case(self.owner_id, self.domain)
        elif self.owner_doc_type == 'CommCareUser':
            from corehq.apps.users.models import CommCareUser
            return CommCareUser.get(self.owner_id)
        elif self.owner_doc_type == 'WebUser':
            from corehq.apps.users.models import WebUser
            return WebUser.get(self.owner_id)
        else:
            return None

    def retire(self):
        self.delete()

    @classmethod
    def by_extensive_search(cls, phone_number):
        p = cls.get_two_way_number(phone_number)

        # If not found, try to see if any number in the database is a substring
        # of the number given to us. This can happen if the telco prepends some
        # international digits, such as 011...
        if not p:
            p = cls.get_two_way_number(phone_number[1:])
        if not p:
            p = cls.get_two_way_number(phone_number[2:])
        if not p:
            p = cls.get_two_way_number(phone_number[3:])

        # If still not found, try to match only the last digits of numbers in
        # the database. This can happen if the telco removes the country code
        # in the caller id.
        if not p:
            p = cls.get_two_way_number_by_suffix(phone_number)

        return p

    @classmethod
    def by_couch_id(cls, couch_id):
        try:
            return cls.objects.get(couch_id=couch_id)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_two_way_number(cls, phone_number):
        return cls._get_two_way_number(apply_leniency(phone_number))

    @classmethod
    @quickcache(['phone_number'], timeout=60 * 60)
    def _get_two_way_number(cls, phone_number):
        with CriticalSection(['PhoneNumber-CacheAccessor-get_two_way_number-%s' % phone_number]):
            try:
                return cls.objects.get(phone_number=phone_number, is_two_way=True)
            except cls.DoesNotExist:
                return None

    @classmethod
    def get_number_pending_verification(cls, phone_number):
        return cls._get_number_pending_verification(apply_leniency(phone_number))

    @classmethod
    @quickcache(['phone_number'], timeout=60 * 60)
    def _get_number_pending_verification(cls, phone_number):
        with CriticalSection(['PhoneNumber-CacheAccessor-get_number_pending_verification-%s' % phone_number]):
            try:
                return cls.objects.get(
                    phone_number=phone_number,
                    verified=False,
                    pending_verification=True
                )
            except cls.DoesNotExist:
                return None

    @classmethod
    def get_reserved_number(cls, phone_number):
        return (
            cls.get_two_way_number(phone_number)
            or cls.get_number_pending_verification(phone_number)
        )

    @classmethod
    def get_two_way_number_with_domain_scope(cls, phone_number, domains):
        phone_number = apply_leniency(phone_number)
        return (cls
                .objects
                .filter(phone_number=phone_number, domain__in=domains)
                .order_by('-is_two_way', 'created_on', 'couch_id')
                .first())

    @classmethod
    def get_two_way_number_by_suffix(cls, phone_number):
        """
        Used to lookup a two-way PhoneNumber, trying to exclude country code digits.

        Decided not to cache this method since in order to clear the cache
        we'd have to clear using all suffixes of a number (which would involve
        up to ~10 cache clear calls on each save). Since this method is used so
        infrequently, it's better to not cache vs. clear so many keys on each
        save. Once all of our IVR gateways provide reliable caller id info,
        we can also remove this method.
        """
        phone_number = apply_leniency(phone_number)
        try:
            return cls.objects.get(phone_number__endswith=phone_number, is_two_way=True)
        except cls.DoesNotExist:
            return None
        except cls.MultipleObjectsReturned:
            return None

    @classmethod
    def by_domain(cls, domain, ids_only=False):
        qs = cls.objects.filter(domain=domain)
        if ids_only:
            return qs.values_list('couch_id', flat=True)
        else:
            return qs

    @classmethod
    def count_by_domain(cls, domain):
        return cls.by_domain(domain).count()

    @classmethod
    @quickcache(['owner_id'], timeout=60 * 60)
    def by_owner_id(cls, owner_id):
        """
        Returns all phone numbers belonging to the given contact.
        """
        with CriticalSection(['PhoneNumber-CacheAccessor-by_owner_id-%s' % owner_id]):
            return list(cls.objects.filter(owner_id=owner_id))

    @classmethod
    def get_phone_number_for_owner(cls, owner_id, phone_number):
        try:
            return cls.objects.get(
                owner_id=owner_id,
                phone_number=apply_leniency(phone_number)
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def _clear_quickcaches(cls, owner_id, phone_number, old_owner_id=None, old_phone_number=None):
        cls.by_owner_id.clear(cls, owner_id)
        if old_owner_id and old_owner_id != owner_id:
            cls.by_owner_id.clear(cls, old_owner_id)

        cls._get_two_way_number.clear(cls, phone_number)
        cls._get_number_pending_verification.clear(cls, phone_number)
        if old_phone_number and old_phone_number != phone_number:
            cls._get_two_way_number.clear(cls, old_phone_number)
            cls._get_number_pending_verification.clear(cls, old_phone_number)

    def _clear_caches(self):
        self._clear_quickcaches(
            self.owner_id,
            self.phone_number,
            old_owner_id=self._old_owner_id,
            old_phone_number=self._old_phone_number
        )

    @property
    def cache_accessor_lock_keys(self):
        keys = [
            'PhoneNumber-CacheAccessor-by_owner_id-%s' % self.owner_id,
            'PhoneNumber-CacheAccessor-get_two_way_number-%s' % self.phone_number,
            'PhoneNumber-CacheAccessor-get_number_pending_verification-%s' % self.phone_number,
        ]

        if self._old_owner_id and self._old_owner_id != self.owner_id:
            keys.extend([
                'PhoneNumber-CacheAccessor-by_owner_id-%s' % self._old_owner_id,
            ])

        if self._old_phone_number and self._old_phone_number != self.phone_number:
            keys.extend([
                'PhoneNumber-CacheAccessor-get_two_way_number-%s' % self._old_phone_number,
                'PhoneNumber-CacheAccessor-get_number_pending_verification-%s' % self._old_phone_number,
            ])

        return keys

    def save(self, *args, **kwargs):
        with CriticalSection(self.cache_accessor_lock_keys):
            # Clearing the cache and updating the DB needs to be an atomic operation
            # otherwise we end up with race conditions where a different method with
            # a cached result is building a queryset with missing data and ends up
            # writing it to the cache.
            self._clear_caches()
            self._old_phone_number = self.phone_number
            self._old_owner_id = self.owner_id
            return super(PhoneNumber, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with CriticalSection(self.cache_accessor_lock_keys):
            self._clear_caches()
            return super(PhoneNumber, self).delete(*args, **kwargs)

    def verify_uniqueness(self):
        entry = self.get_reserved_number(self.phone_number)
        if entry and entry.pk != self.pk:
            raise PhoneNumberInUseException()

    def set_two_way(self):
        if self.is_two_way:
            return

        with CriticalSection(['reserve-phone-number-%s' % self.phone_number]):
            self.verify_uniqueness()
            self.is_two_way = True
            self.save()

    def set_pending_verification(self):
        if self.verified or self.pending_verification:
            return

        with CriticalSection(['reserve-phone-number-%s' % self.phone_number]):
            self.verify_uniqueness()
            self.pending_verification = True
            self.save()

    def set_verified(self):
        self.verified = True
        self.pending_verification = False


class MessagingStatusMixin(object):

    def refresh(self):
        return self.__class__.objects.get(pk=self.pk)

    def error(self, error_code, additional_error_text=None, status=None):
        if status is None:
            self.status = MessagingEvent.STATUS_ERROR
        else:
            self.status = status
        self.error_code = error_code
        self.additional_error_text = additional_error_text
        self.save()

    def completed(self):
        obj = self.refresh()
        if obj.status != MessagingEvent.STATUS_ERROR:
            obj.status = MessagingEvent.STATUS_COMPLETED
            obj.save()
        return obj


class MessagingEvent(models.Model, MessagingStatusMixin):
    """
    Used to track the status of high-level events in the messaging
    framework. Examples of such high-level events include the firing
    of a reminder instance, the invoking of a keyword, or the sending
    of a broadcast.
    """
    STATUS_IN_PROGRESS = 'PRG'
    STATUS_COMPLETED = 'CMP'
    STATUS_NOT_COMPLETED = 'NOT'
    STATUS_ERROR = 'ERR'
    STATUS_EMAIL_SENT = 'SND'
    STATUS_EMAIL_DELIVERED = 'DEL'

    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, gettext_noop('In Progress')),
        (STATUS_COMPLETED, gettext_noop('Completed')),
        (STATUS_NOT_COMPLETED, gettext_noop('Not Completed')),
        (STATUS_ERROR, gettext_noop('Error')),
        (STATUS_EMAIL_SENT, gettext_noop('Email Sent')),
        (STATUS_EMAIL_DELIVERED, gettext_noop('Email Delivered')),
    )

    STATUS_SLUGS = {
        STATUS_IN_PROGRESS: "in-progress",
        STATUS_COMPLETED: "completed",
        STATUS_NOT_COMPLETED: "not-completed",
        STATUS_ERROR: "error",
        STATUS_EMAIL_SENT: "email-sent",
        STATUS_EMAIL_DELIVERED: "email-delivered",
    }

    SOURCE_BROADCAST = 'BRD'
    SOURCE_KEYWORD = 'KWD'
    SOURCE_REMINDER = 'RMD'
    SOURCE_UNRECOGNIZED = 'UNR'
    SOURCE_FORWARDED = 'FWD'
    SOURCE_OTHER = 'OTH'
    SOURCE_SCHEDULED_BROADCAST = 'SBR'
    SOURCE_IMMEDIATE_BROADCAST = 'IBR'
    SOURCE_CASE_RULE = 'CRL'

    SOURCE_CHOICES = (
        (SOURCE_BROADCAST, gettext_noop('Broadcast')),
        (SOURCE_SCHEDULED_BROADCAST, gettext_noop('Scheduled Broadcast')),
        (SOURCE_IMMEDIATE_BROADCAST, gettext_noop('Immediate Broadcast')),
        (SOURCE_KEYWORD, gettext_noop('Keyword')),
        (SOURCE_REMINDER, gettext_noop('Reminder')),
        (SOURCE_CASE_RULE, gettext_noop('Conditional Alert')),
        (SOURCE_UNRECOGNIZED, gettext_noop('Unrecognized')),
        (SOURCE_FORWARDED, gettext_noop('Forwarded Message')),
        (SOURCE_OTHER, gettext_noop('Other')),
    )

    SOURCE_SLUGS = {
        SOURCE_BROADCAST: 'broadcast',
        SOURCE_SCHEDULED_BROADCAST: 'scheduled-broadcast',
        SOURCE_IMMEDIATE_BROADCAST: 'immediate-broadcast',
        SOURCE_KEYWORD: 'keyword',
        SOURCE_REMINDER: 'reminder',
        SOURCE_CASE_RULE: 'conditional-alert',
        SOURCE_UNRECOGNIZED: 'unrecognized',
        SOURCE_FORWARDED: 'forwarded-message',
        SOURCE_OTHER: 'other',
    }

    CONTENT_NONE = 'NOP'
    CONTENT_SMS = 'SMS'
    CONTENT_SMS_CALLBACK = 'CBK'
    CONTENT_SMS_SURVEY = 'SVY'
    CONTENT_IVR_SURVEY = 'IVR'
    CONTENT_PHONE_VERIFICATION = 'VER'
    CONTENT_ADHOC_SMS = 'ADH'
    CONTENT_API_SMS = 'API'
    CONTENT_CHAT_SMS = 'CHT'
    CONTENT_EMAIL = 'EML'
    CONTENT_FCM_Notification = 'FCM'

    CONTENT_CHOICES = (
        (CONTENT_NONE, gettext_noop('None')),
        (CONTENT_SMS, gettext_noop('SMS Message')),
        (CONTENT_SMS_CALLBACK, gettext_noop('SMS Expecting Callback')),
        (CONTENT_SMS_SURVEY, gettext_noop('SMS Survey')),
        (CONTENT_IVR_SURVEY, gettext_noop('IVR Survey')),
        (CONTENT_PHONE_VERIFICATION, gettext_noop('Phone Verification')),
        (CONTENT_ADHOC_SMS, gettext_noop('Manually Sent Message')),
        (CONTENT_API_SMS, gettext_noop('Message Sent Via API')),
        (CONTENT_CHAT_SMS, gettext_noop('Message Sent Via Chat')),
        (CONTENT_EMAIL, gettext_noop('Email')),
        (CONTENT_FCM_Notification, gettext_noop('FCM Push Notification')),
    )

    CONTENT_TYPE_SLUGS = {
        CONTENT_NONE: "none",
        CONTENT_SMS: "sms",
        CONTENT_SMS_CALLBACK: "sms-callback",
        CONTENT_SMS_SURVEY: "sms-survey",
        CONTENT_IVR_SURVEY: "ivr-survey",
        CONTENT_PHONE_VERIFICATION: "phone-verification",
        CONTENT_ADHOC_SMS: "manual-sms",
        CONTENT_API_SMS: "api-sms",
        CONTENT_CHAT_SMS: "chat-sms",
        CONTENT_EMAIL: "email",
        CONTENT_FCM_Notification: 'fcm-notification',
    }

    RECIPIENT_CASE = 'CAS'
    RECIPIENT_MOBILE_WORKER = 'MOB'
    RECIPIENT_WEB_USER = 'WEB'
    RECIPIENT_USER_GROUP = 'UGP'
    RECIPIENT_CASE_GROUP = 'CGP'
    RECIPIENT_VARIOUS = 'MUL'
    RECIPIENT_LOCATION = 'LOC'
    RECIPIENT_LOCATION_PLUS_DESCENDANTS = 'LC+'
    RECIPIENT_VARIOUS_LOCATIONS = 'VLC'
    RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS = 'VL+'
    RECIPIENT_UNKNOWN = 'UNK'

    RECIPIENT_CHOICES = (
        (RECIPIENT_CASE, gettext_noop('Case')),
        (RECIPIENT_MOBILE_WORKER, gettext_noop('Mobile Worker')),
        (RECIPIENT_WEB_USER, gettext_noop('Web User')),
        (RECIPIENT_USER_GROUP, gettext_noop('User Group')),
        (RECIPIENT_CASE_GROUP, gettext_noop('Case Group')),
        (RECIPIENT_VARIOUS, gettext_noop('Multiple Recipients')),
        (RECIPIENT_LOCATION, gettext_noop('Location')),
        (RECIPIENT_LOCATION_PLUS_DESCENDANTS,
            gettext_noop('Location (including child locations)')),
        (RECIPIENT_VARIOUS_LOCATIONS, gettext_noop('Multiple Locations')),
        (RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS,
            gettext_noop('Multiple Locations (including child locations)')),
        (RECIPIENT_UNKNOWN, gettext_noop('Unknown Contact')),
    )

    ERROR_NO_RECIPIENT = 'NO_RECIPIENT'
    ERROR_NO_MESSAGE = 'NO_MESSAGE'
    ERROR_CANNOT_RENDER_MESSAGE = 'CANNOT_RENDER_MESSAGE'
    ERROR_UNSUPPORTED_COUNTRY = 'UNSUPPORTED_COUNTRY'
    ERROR_NO_PHONE_NUMBER = 'NO_PHONE_NUMBER'
    ERROR_NO_TWO_WAY_PHONE_NUMBER = 'NO_TWO_WAY_PHONE_NUMBER'
    ERROR_PHONE_OPTED_OUT = 'PHONE_OPTED_OUT'
    ERROR_INVALID_CUSTOM_CONTENT_HANDLER = 'INVALID_CUSTOM_CONTENT_HANDLER'
    ERROR_CANNOT_LOAD_CUSTOM_CONTENT_HANDLER = 'CANNOT_LOAD_CUSTOM_CONTENT_HANDLER'
    ERROR_CANNOT_FIND_FORM = 'CANNOT_FIND_FORM'
    ERROR_FORM_HAS_NO_QUESTIONS = 'FORM_HAS_NO_QUESTIONS'
    ERROR_CASE_EXTERNAL_ID_NOT_FOUND = 'CASE_EXTERNAL_ID_NOT_FOUND'
    ERROR_MULTIPLE_CASES_WITH_EXTERNAL_ID_FOUND = 'MULTIPLE_CASES_WITH_EXTERNAL_ID_FOUND'
    ERROR_NO_CASE_GIVEN = 'NO_CASE_GIVEN'
    ERROR_NO_EXTERNAL_ID_GIVEN = 'NO_EXTERNAL_ID_GIVEN'
    ERROR_COULD_NOT_PROCESS_STRUCTURED_SMS = 'COULD_NOT_PROCESS_STRUCTURED_SMS'
    ERROR_SUBEVENT_ERROR = 'SUBEVENT_ERROR'
    ERROR_TOUCHFORMS_ERROR = 'TOUCHFORMS_ERROR'
    ERROR_INTERNAL_SERVER_ERROR = 'INTERNAL_SERVER_ERROR'
    ERROR_NO_SUITABLE_GATEWAY = 'NO_SUITABLE_GATEWAY'
    ERROR_GATEWAY_NOT_FOUND = 'GATEWAY_NOT_FOUND'
    ERROR_NO_EMAIL_ADDRESS = 'NO_EMAIL_ADDRESS'
    ERROR_INVALID_EMAIL_ADDRESS = 'ERROR_INVALID_EMAIL_ADDRESS'
    ERROR_TRIAL_EMAIL_LIMIT_REACHED = 'TRIAL_EMAIL_LIMIT_REACHED'
    ERROR_EMAIL_BOUNCED = 'EMAIL_BOUNCED'
    ERROR_EMAIL_GATEWAY = 'EMAIL_GATEWAY_ERROR'
    ERROR_NO_FCM_TOKENS = 'NO_FCM_TOKENS'
    ERROR_FCM_NOT_AVAILABLE = 'FCM_NOT_AVAILABLE'
    ERROR_FCM_UNSUPPORTED_RECIPIENT = 'FCM_UNSUPPORTED_RECIPIENT'
    ERROR_FCM_NO_ACTION = "FCM_NO_ACTION"
    ERROR_FCM_NOTIFICATION_FAILURE = "FCM_NOTIFICATION_FAILURE"
    ERROR_FCM_DOMAIN_NOT_ENABLED = 'FCM_DOMAIN_NOT_ENABLED'

    ERROR_MESSAGES = {
        ERROR_NO_RECIPIENT:
            gettext_noop('No recipient'),
        ERROR_NO_MESSAGE:
            gettext_noop('No message available for the given language settings.'),
        ERROR_CANNOT_RENDER_MESSAGE:
            gettext_noop('Error rendering message; please check syntax.'),
        ERROR_UNSUPPORTED_COUNTRY:
            gettext_noop('Gateway does not support the destination country.'),
        ERROR_NO_PHONE_NUMBER:
            gettext_noop('Contact has no phone number.'),
        ERROR_NO_TWO_WAY_PHONE_NUMBER:
            gettext_noop('Contact has no two-way phone number.'),
        ERROR_PHONE_OPTED_OUT:
            gettext_noop('Phone number has opted out of receiving SMS.'),
        ERROR_INVALID_CUSTOM_CONTENT_HANDLER:
            gettext_noop('Invalid custom content handler.'),
        ERROR_CANNOT_LOAD_CUSTOM_CONTENT_HANDLER:
            gettext_noop('Cannot load custom content handler.'),
        ERROR_CANNOT_FIND_FORM:
            gettext_noop('Cannot find form.'),
        ERROR_FORM_HAS_NO_QUESTIONS:
            gettext_noop('No questions were available in the form. Please '
                'check that the form has questions and that display conditions '
                'are not preventing questions from being asked.'),
        ERROR_CASE_EXTERNAL_ID_NOT_FOUND:
            gettext_noop('The case with the given external ID was not found.'),
        ERROR_MULTIPLE_CASES_WITH_EXTERNAL_ID_FOUND:
            gettext_noop('Multiple cases were found with the given external ID.'),
        ERROR_NO_CASE_GIVEN:
            gettext_noop('The form requires a case but no case was provided.'),
        ERROR_NO_EXTERNAL_ID_GIVEN:
            gettext_noop('No external ID given; please include case external ID after keyword.'),
        ERROR_COULD_NOT_PROCESS_STRUCTURED_SMS:
            gettext_noop('Error processing structured SMS.'),
        ERROR_SUBEVENT_ERROR:
            gettext_noop('View details for more information.'),
        ERROR_TOUCHFORMS_ERROR:
            gettext_noop('An error occurred in the formplayer service.'),
        ERROR_INTERNAL_SERVER_ERROR:
            gettext_noop('Internal Server Error'),
        ERROR_NO_SUITABLE_GATEWAY:
            gettext_noop('No suitable gateway could be found.'),
        ERROR_GATEWAY_NOT_FOUND:
            gettext_noop('Gateway could not be found.'),
        ERROR_NO_EMAIL_ADDRESS:
            gettext_noop('Recipient has no email address.'),
        ERROR_INVALID_EMAIL_ADDRESS:
            gettext_noop("Recipient's email address is not valid."),
        ERROR_TRIAL_EMAIL_LIMIT_REACHED:
            gettext_noop("Cannot send any more reminder emails. The limit for "
                "sending reminder emails on a Trial plan has been reached."),
        ERROR_EMAIL_BOUNCED: gettext_noop("Email Bounced"),
        ERROR_EMAIL_GATEWAY: gettext_noop("Email Gateway Error"),
        ERROR_NO_FCM_TOKENS: gettext_noop("No FCM tokens found for recipient."),
        ERROR_FCM_NOT_AVAILABLE: gettext_noop("FCM not available on this environment."),
        ERROR_FCM_UNSUPPORTED_RECIPIENT: gettext_noop("FCM is supported for Mobile Workers only."),
        ERROR_FCM_NO_ACTION: gettext_noop("No action selected for the FCM Data message type."),
        ERROR_FCM_NOTIFICATION_FAILURE: gettext_noop("Failure while sending FCM notifications to the devices."),
        ERROR_FCM_DOMAIN_NOT_ENABLED: gettext_noop("Domain is not enabled for FCM Push Notifications"),
    }

    domain = models.CharField(max_length=126, null=False, db_index=True)
    date = models.DateTimeField(null=False, db_index=True)
    source = models.CharField(max_length=3, null=False)
    source_id = models.CharField(max_length=126, null=True)
    content_type = models.CharField(max_length=3, choices=CONTENT_CHOICES, null=False)

    # Only used when content_type is CONTENT_SMS_SURVEY or CONTENT_IVR_SURVEY
    # This is redundantly stored here (as well as the subevent) so that it
    # doesn't have to be looked up for reporting.
    app_id = models.CharField(max_length=126, null=True)
    form_unique_id = models.CharField(max_length=126, null=True)
    form_name = models.TextField(null=True)

    # If any of the MessagingSubEvent status's are STATUS_ERROR, this is STATUS_ERROR
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, null=False)
    error_code = models.CharField(max_length=126, null=True)
    additional_error_text = models.TextField(null=True)
    recipient_type = models.CharField(max_length=3, choices=RECIPIENT_CHOICES, null=True, db_index=True)
    recipient_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta(object):
        app_label = 'sms'

    def get_source_display(self):
        # for some reason source choices aren't set in the field, so manually add this method.
        # to mimic _get_FIELD_display in django.models.base.Model
        # https://github.com/django/django/blob/main/django/db/models/base.py#L962-L966
        return force_str(dict(self.SOURCE_CHOICES).get(self.source, self.source), strings_only=True)

    @classmethod
    def get_recipient_type_from_doc_type(cls, recipient_doc_type):
        return {
            'CommCareUser': cls.RECIPIENT_MOBILE_WORKER,
            'WebUser': cls.RECIPIENT_WEB_USER,
            'CommCareCase': cls.RECIPIENT_CASE,
            'Group': cls.RECIPIENT_USER_GROUP,
            'CommCareCaseGroup': cls.RECIPIENT_CASE_GROUP,
        }.get(recipient_doc_type, cls.RECIPIENT_UNKNOWN)

    @classmethod
    def get_recipient_type(cls, recipient):
        return cls.get_recipient_type_from_doc_type(recipient.doc_type)

    @classmethod
    def _get_recipient_doc_type(cls, recipient_type):
        return {
            MessagingEvent.RECIPIENT_MOBILE_WORKER: 'CommCareUser',
            MessagingEvent.RECIPIENT_WEB_USER: 'WebUser',
            MessagingEvent.RECIPIENT_CASE: 'CommCareCase',
            MessagingEvent.RECIPIENT_USER_GROUP: 'Group',
            MessagingEvent.RECIPIENT_CASE_GROUP: 'CommCareCaseGroup',
            MessagingEvent.RECIPIENT_LOCATION: 'SQLLocation',
            MessagingEvent.RECIPIENT_LOCATION_PLUS_DESCENDANTS: 'SQLLocation',
        }.get(recipient_type, None)

    def get_recipient_doc_type(self):
        return MessagingEvent._get_recipient_doc_type(self.recipient_type)

    @classmethod
    def create_event_for_adhoc_sms(cls, domain, recipient=None,
            content_type=CONTENT_ADHOC_SMS, source=SOURCE_OTHER):
        if recipient:
            recipient_type = cls.get_recipient_type(recipient)
            recipient_id = recipient.get_id
        else:
            recipient_type = cls.RECIPIENT_UNKNOWN
            recipient_id = None

        obj = cls.objects.create(
            domain=domain,
            date=datetime.utcnow(),
            source=source,
            content_type=content_type,
            status=cls.STATUS_IN_PROGRESS,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
        )
        return obj

    def create_structured_sms_subevent(self, case_id):
        obj = MessagingSubEvent.objects.create(
            parent=self,
            domain=self.domain,
            date=datetime.utcnow(),
            recipient_type=self.recipient_type,
            recipient_id=self.recipient_id,
            content_type=MessagingEvent.CONTENT_SMS_SURVEY,
            app_id=self.app_id,
            form_unique_id=self.form_unique_id,
            form_name=self.form_name,
            case_id=case_id,
            status=MessagingEvent.STATUS_IN_PROGRESS,
        )
        return obj

    def create_subevent_for_single_sms(self, recipient_doc_type=None,
            recipient_id=None, case=None, completed=False):
        obj = MessagingSubEvent.objects.create(
            parent=self,
            domain=self.domain,
            date=datetime.utcnow(),
            recipient_type=MessagingEvent.get_recipient_type_from_doc_type(recipient_doc_type),
            recipient_id=recipient_id,
            content_type=MessagingEvent.CONTENT_SMS,
            case_id=case.case_id if case else None,
            status=(MessagingEvent.STATUS_COMPLETED
                    if completed
                    else MessagingEvent.STATUS_IN_PROGRESS),
        )
        return obj

    @property
    def subevents(self):
        return self.messagingsubevent_set.all()

    @classmethod
    def get_form_name_or_none(cls, domain, app_id, form_unique_id):
        try:
            app = get_app(domain, app_id)
            form = app.get_form(form_unique_id)
            return form.full_path_name
        except Exception:
            return None

    @classmethod
    def get_content_info_from_keyword(cls, keyword):
        content_type = cls.CONTENT_NONE
        app_id = None
        form_unique_id = None
        form_name = None

        for action in keyword.keywordaction_set.all():
            if action.recipient == KeywordAction.RECIPIENT_SENDER:
                if action.action in (KeywordAction.ACTION_SMS_SURVEY, KeywordAction.ACTION_STRUCTURED_SMS):
                    content_type = cls.CONTENT_SMS_SURVEY
                    app_id = action.app_id
                    form_unique_id = action.form_unique_id
                    form_name = cls.get_form_name_or_none(keyword.domain, action.app_id, action.form_unique_id)
                elif action.action == KeywordAction.ACTION_SMS:
                    content_type = cls.CONTENT_SMS

        return (content_type, app_id, form_unique_id, form_name)

    @classmethod
    def get_source_and_id_from_schedule_instance(cls, schedule_instance):
        from corehq.messaging.scheduling.models import (
            ImmediateBroadcast,
            ScheduledBroadcast,
        )
        from corehq.messaging.scheduling.scheduling_partitioned.models import (
            AlertScheduleInstance,
            TimedScheduleInstance,
            CaseAlertScheduleInstance,
            CaseTimedScheduleInstance,
        )

        if isinstance(schedule_instance, AlertScheduleInstance):
            source_id = (
                ImmediateBroadcast
                .objects
                .filter(schedule_id=schedule_instance.alert_schedule_id)
                .values_list('id', flat=True)
                .first()
            )
            return cls.SOURCE_IMMEDIATE_BROADCAST, source_id
        elif isinstance(schedule_instance, TimedScheduleInstance):
            source_id = (
                ScheduledBroadcast
                .objects
                .filter(schedule_id=schedule_instance.timed_schedule_id)
                .values_list('id', flat=True)
                .first()
            )
            return cls.SOURCE_SCHEDULED_BROADCAST, source_id
        elif isinstance(schedule_instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
            return cls.SOURCE_CASE_RULE, schedule_instance.rule_id
        else:
            return cls.SOURCE_UNRECOGNIZED, None

    @classmethod
    def get_content_info_from_content_object(cls, domain, content):
        from corehq.messaging.scheduling.models import (
            SMSContent,
            SMSSurveyContent,
            EmailContent,
            CustomContent,
            FCMNotificationContent,
        )

        if isinstance(content, (SMSContent, CustomContent)):
            return cls.CONTENT_SMS, None, None, None
        elif isinstance(content, SMSSurveyContent):
            app, module, form, requires_input = content.get_memoized_app_module_form(domain)
            form_name = form.full_path_name if form else None
            return cls.CONTENT_SMS_SURVEY, content.app_id, content.form_unique_id, form_name
        elif isinstance(content, EmailContent):
            return cls.CONTENT_EMAIL, None, None, None
        elif isinstance(content, FCMNotificationContent):
            return cls.CONTENT_FCM_Notification, None, None, None
        else:
            return cls.CONTENT_NONE, None, None, None

    @classmethod
    def get_recipient_type_and_id_from_schedule_instance(cls, schedule_instance):
        from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

        if isinstance(schedule_instance.recipient, list):
            recipient_type = cls.RECIPIENT_VARIOUS
            recipient_id = None
        elif isinstance(schedule_instance.recipient, SQLLocation):
            # schedule_instance.recipient can be a SQLLocation in a number of special
            # cases, for example if a case owner is a location, or if a custom recipient
            # is a location. We only count the include_descendant_locations flag when
            # the recipient_type is RECIPIENT_TYPE_LOCATION.
            if (
                schedule_instance.recipient_type == ScheduleInstance.RECIPIENT_TYPE_LOCATION
                and schedule_instance.memoized_schedule.include_descendant_locations
            ):
                recipient_type = cls.RECIPIENT_LOCATION_PLUS_DESCENDANTS
            else:
                recipient_type = cls.RECIPIENT_LOCATION

            recipient_id = schedule_instance.recipient.location_id
        elif schedule_instance.recipient is None:
            recipient_type = cls.RECIPIENT_UNKNOWN
            recipient_id = None
        else:
            recipient_type = cls.get_recipient_type(schedule_instance.recipient)
            recipient_id = schedule_instance.recipient.get_id if recipient_type else None

        return recipient_type, recipient_id

    @classmethod
    def create_from_schedule_instance(cls, schedule_instance, content):
        source, source_id = cls.get_source_and_id_from_schedule_instance(schedule_instance)
        content_type, app_id, form_unique_id, form_name = (
            cls.get_content_info_from_content_object(schedule_instance.domain, content)
        )

        recipient_type, recipient_id = (
            cls.get_recipient_type_and_id_from_schedule_instance(schedule_instance)
        )

        return cls.objects.create(
            domain=schedule_instance.domain,
            date=datetime.utcnow(),
            source=source,
            source_id=source_id,
            content_type=content_type,
            app_id=app_id,
            form_unique_id=form_unique_id,
            form_name=form_name,
            status=cls.STATUS_IN_PROGRESS,
            recipient_type=recipient_type,
            recipient_id=recipient_id
        )

    def create_subevent_from_contact_and_content(self, contact, content, case_id=None):
        """
        In the subevent context, the contact is always going to either be
        a user or a case.

        content is an instance of a subclass of corehq.messaging.scheduling.models.Content
        """
        recipient_type = self.get_recipient_type(contact)

        content_type, app_id, form_unique_id, form_name = (
            self.get_content_info_from_content_object(self.domain, content)
        )

        return MessagingSubEvent.objects.create(
            parent=self,
            domain=self.domain,
            date=datetime.utcnow(),
            recipient_type=recipient_type,
            recipient_id=contact.get_id if recipient_type else None,
            content_type=content_type,
            app_id=app_id,
            form_unique_id=form_unique_id,
            form_name=form_name,
            case_id=case_id,
            status=self.STATUS_IN_PROGRESS,
        )

    @classmethod
    def create_from_keyword(cls, keyword, contact):
        """
        keyword - the keyword object
        contact - the person who initiated the keyword
        """
        content_type, app_id, form_unique_id, form_name = cls.get_content_info_from_keyword(keyword)
        recipient_type = cls.get_recipient_type(contact)

        return cls.objects.create(
            domain=keyword.domain,
            date=datetime.utcnow(),
            source=cls.SOURCE_KEYWORD,
            source_id=keyword.couch_id,
            content_type=content_type,
            app_id=app_id,
            form_unique_id=form_unique_id,
            form_name=form_name,
            status=cls.STATUS_IN_PROGRESS,
            recipient_type=recipient_type,
            recipient_id=contact.get_id if recipient_type else None
        )

    @classmethod
    def create_verification_event(cls, domain, contact):
        recipient_type = cls.get_recipient_type(contact)
        return cls.objects.create(
            domain=domain,
            date=datetime.utcnow(),
            source=cls.SOURCE_OTHER,
            content_type=cls.CONTENT_PHONE_VERIFICATION,
            status=cls.STATUS_IN_PROGRESS,
            recipient_type=recipient_type,
            recipient_id=contact.get_id if recipient_type else None
        )

    @classmethod
    def get_current_verification_event(cls, domain, contact_id, phone_number):
        """
        Returns the latest phone verification event that is in progress
        for the given contact and phone number, or None if one does not exist.
        """
        qs = cls.objects.filter(
            domain=domain,
            recipient_id=contact_id,
            messagingsubevent__sms__phone_number=smsutil.clean_phone_number(phone_number),
            content_type=cls.CONTENT_PHONE_VERIFICATION,
            status=cls.STATUS_IN_PROGRESS
        )
        return qs.order_by('-date')[0] if qs.count() > 0 else None

    @staticmethod
    def get_counts_by_date(domain, start_date, end_date, time_zone):
        """
        Retrieves counts of messaging events at the subevent level over the
        given date range for the given domain.

        :param domain: the domain
        :param start_date: the start date, as a date type
        :param end_date: the end date (inclusive), as a date type
        :param time_zone: the time zone to use when grouping counts by date,
        as a string type (e.g., 'America/New_York')

        :return: A list of (date, error_count, total_count) named tuples
        """

        CountTuple = namedtuple('CountTuple', ['date', 'error_count', 'total_count'])

        query = """
        SELECT      (A.date AT TIME ZONE %s)::DATE AS date,
                    SUM(
                        CASE
                        WHEN B.status = 'ERR' OR C.error OR (B.id IS NULL AND A.status = 'ERR')
                        THEN 1
                        ELSE 0
                        END
                    ) AS error_count,
                    COUNT(*) AS total_count
        FROM        sms_messagingevent A
        LEFT JOIN   sms_messagingsubevent B
        ON          A.id = B.parent_id
        LEFT JOIN   sms_sms C
        ON          B.id = C.messaging_subevent_id
        WHERE       A.domain = %s
        AND         A.date >= (%s + TIME '00:00') AT TIME ZONE %s
        AND         A.date < (%s + 1 + TIME '00:00') AT TIME ZONE %s
        GROUP BY    1
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [time_zone, domain, start_date, time_zone, end_date, time_zone]
            )
            return [CountTuple(*row) for row in cursor.fetchall()]

    @classmethod
    def get_counts_of_errors(cls, domain, start_date, end_date, time_zone):
        """
        Retrieves counts of errors at the event, subevent, or sms levels over the
        given date range for the given domain.

        :param domain: the domain
        :param start_date: the start date, as a date type
        :param end_date: the end date (inclusive), as a date type
        :param time_zone: the time zone to use when filtering,
        as a string type (e.g., 'America/New_York')

        :return: A dictionary with each key being an error code and each value
        being the count of that error's occurrences
        """

        query = """
        SELECT      COALESCE(C.system_error_message, B.error_code, A.error_code) AS error,
                    COUNT(*) AS count
        FROM        sms_messagingevent A
        LEFT JOIN   sms_messagingsubevent B
        ON          A.id = B.parent_id
        LEFT JOIN   sms_sms C
        ON          B.id = C.messaging_subevent_id
        WHERE       A.domain = %s
        AND         A.date >= (%s + TIME '00:00') AT TIME ZONE %s
        AND         A.date < (%s + 1 + TIME '00:00') AT TIME ZONE %s
        GROUP BY    1
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [domain, start_date, time_zone, end_date, time_zone]
            )
            return {
                error: count
                for error, count in cursor.fetchall()
                if error and error != cls.ERROR_SUBEVENT_ERROR
            }


class MessagingSubEvent(models.Model, MessagingStatusMixin):
    """
    Used to track the status of a MessagingEvent for each of its recipients.
    """
    RECIPIENT_CHOICES = (
        (MessagingEvent.RECIPIENT_CASE, gettext_noop('Case')),
        (MessagingEvent.RECIPIENT_MOBILE_WORKER, gettext_noop('Mobile Worker')),
        (MessagingEvent.RECIPIENT_WEB_USER, gettext_noop('Web User')),
    )

    RECIPIENT_SLUGS = {
        MessagingEvent.RECIPIENT_CASE: 'case',
        MessagingEvent.RECIPIENT_MOBILE_WORKER: 'mobile-worker',
        MessagingEvent.RECIPIENT_WEB_USER: 'web-user',
    }

    parent = models.ForeignKey('MessagingEvent', on_delete=models.CASCADE)
    domain = models.CharField(max_length=126, null=True)
    date = models.DateTimeField(null=False, db_index=True)
    date_last_activity = models.DateTimeField(null=True, auto_now=True)
    recipient_type = models.CharField(max_length=3, choices=RECIPIENT_CHOICES, null=False)
    recipient_id = models.CharField(max_length=126, null=True)
    content_type = models.CharField(max_length=3, choices=MessagingEvent.CONTENT_CHOICES, null=False)

    # Only used when content_type is CONTENT_SMS_SURVEY or CONTENT_IVR_SURVEY
    app_id = models.CharField(max_length=126, null=True)
    form_unique_id = models.CharField(max_length=126, null=True)
    form_name = models.TextField(null=True)
    xforms_session = models.ForeignKey('smsforms.SQLXFormsSession', null=True, on_delete=models.PROTECT)

    # If this was a reminder that spawned off of a case, this is the case's id
    case_id = models.CharField(max_length=126, null=True, db_index=True)
    status = models.CharField(max_length=3, choices=MessagingEvent.STATUS_CHOICES, null=False)
    error_code = models.CharField(max_length=126, null=True)
    additional_error_text = models.TextField(null=True)

    class Meta(object):
        app_label = 'sms'
        index_together = (
            # used by the messaging-event api
            ('domain', 'date_last_activity', 'id'),
        )

    def save(self, *args, **kwargs):
        super(MessagingSubEvent, self).save(*args, **kwargs)
        parent = self.parent

        # If this event is in an errored state, also set the parent
        # event to an errored state.
        if self.status == MessagingEvent.STATUS_ERROR:
            parent.status = MessagingEvent.STATUS_ERROR
            parent.save()

        # If the parent event had various recipients, mark it as such,
        # unless the source was a keyword in which case the recipient
        # listed should always be the keyword initiator.
        if (parent.source != MessagingEvent.SOURCE_KEYWORD
                and (parent.recipient_id != self.recipient_id or self.recipient_id is None)
                and parent.recipient_type not in (
                    MessagingEvent.RECIPIENT_USER_GROUP,
                    MessagingEvent.RECIPIENT_CASE_GROUP,
                    MessagingEvent.RECIPIENT_VARIOUS,
                    MessagingEvent.RECIPIENT_LOCATION,
                    MessagingEvent.RECIPIENT_LOCATION_PLUS_DESCENDANTS,
                    MessagingEvent.RECIPIENT_VARIOUS_LOCATIONS,
                    MessagingEvent.RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS,
                ) and len(parent.subevents) > 1):
            parent.recipient_type = MessagingEvent.RECIPIENT_VARIOUS
            parent.recipient_id = None
            parent.save()

    def get_recipient_doc_type(self):
        return MessagingEvent._get_recipient_doc_type(self.recipient_type)

    def update_date_last_activity(self):
        self.save(update_fields=["date_last_activity"])


class ActiveMobileBackendManager(models.Manager):

    def get_queryset(self):
        return super(ActiveMobileBackendManager, self).get_queryset().filter(deleted=False)


class SQLMobileBackend(UUIDGeneratorMixin, models.Model):
    SMS = 'SMS'
    IVR = 'IVR'

    TYPE_CHOICES = (
        (SMS, gettext_lazy('SMS')),
        (IVR, gettext_lazy('IVR')),
    )

    UUIDS_TO_GENERATE = ['couch_id', 'inbound_api_key']

    objects = models.Manager()
    active_objects = ActiveMobileBackendManager()

    # We can't really get rid of this until all the messaging models are in
    # postgres. Once that happens we can migrate references to the couch_id
    # as a foreign key to postgres id and get rid of this field.
    couch_id = models.CharField(max_length=126, db_index=True, unique=True)
    backend_type = models.CharField(max_length=3, choices=TYPE_CHOICES, default=SMS)

    # This is an api key that the gateway uses when making inbound requests to hq.
    # This enforces gateway security and also allows us to tie every inbound request
    # to a specific backend.
    inbound_api_key = models.CharField(max_length=126, unique=True, db_index=True)

    # This tells us which type of backend this is
    hq_api_id = models.CharField(max_length=126, null=True)

    # Global backends are system owned and can be used by anyone
    is_global = models.BooleanField(default=False)

    # This is the domain that the backend belongs to, or None for
    # global backends
    domain = models.CharField(max_length=126, null=True, db_index=True)

    # A short name for a backend instance which is referenced when
    # setting a case contact's preferred backend
    name = models.CharField(max_length=126)

    # Simple name to display to users - e.g. "Twilio"
    display_name = models.CharField(max_length=126, null=True)

    # Optionally, a description of this backend
    description = models.TextField(null=True)

    # A JSON list of countries that this backend supports.
    # This information is displayed in the gateway list UI.
    # If this backend represents an international gateway,
    # set this to: ["*"]
    supported_countries = jsonfield.JSONField(default=list)

    # To avoid having many tables with so few records in them, all
    # SMS backends are stored in this same table. This field is a
    # JSON dict which stores any additional fields that the SMS
    # backend subclasses need.
    # NOTE: Do not access this field directly, instead use get_extra_fields()
    # and set_extra_fields()
    extra_fields = jsonfield.JSONField(default=dict)

    # For a historical view of sms data, we can't delete backends.
    # Instead, set a deleted flag when a backend should no longer be used.
    deleted = models.BooleanField(default=False)

    # If the backend uses load balancing, this is a JSON list of the
    # phone numbers to load balance over.
    load_balancing_numbers = jsonfield.JSONField(default=list)

    # The phone number which you can text to or call in order to reply
    # to this backend
    reply_to_phone_number = models.CharField(max_length=126, null=True)

    # Some backends use their own inbound api key and not the default hq-generated one.
    # For those, we don't show the inbound api key on the edit backend page.
    show_inbound_api_key_during_edit = True

    # Custom opt in/out keywords for gateways that allows users to configure their own at
    # the gateway level, such as twilio advanced opt out
    opt_in_keywords = ArrayField(models.TextField(), default=list)
    opt_out_keywords = ArrayField(models.TextField(), default=list)

    class Meta(object):
        db_table = 'messaging_mobilebackend'
        app_label = 'sms'

    class ExpectedDomainLevelBackend(Exception):
        pass

    def to_json(self):
        from corehq.apps.sms.serializers import MobileBackendSerializer
        data = MobileBackendSerializer(self).data
        return data

    def __str__(self):
        if self.is_global:
            return "Global Backend '%s'" % self.name
        else:
            return "Domain '%s' Backend '%s'" % (self.domain, self.name)

    @quickcache(['self.pk', 'domain'], timeout=5 * 60)
    def domain_is_shared(self, domain):
        """
        Returns True if this backend has been shared with domain and domain
        has accepted the invitation.
        """
        count = self.mobilebackendinvitation_set.filter(domain=domain, accepted=True).count()
        return count > 0

    @property
    def domains_with_access(self):
        if self.is_global:
            raise self.ExpectedDomainLevelBackend()

        return [self.domain] + list(self.get_authorized_domain_list())

    def domain_is_authorized(self, domain):
        """
        Returns True if the given domain is authorized to use this backend.
        """
        return (self.is_global
                or domain == self.domain
                or self.domain_is_shared(domain))

    @classmethod
    def name_is_unique(cls, name, domain=None, backend_id=None):
        if domain:
            result = cls.objects.filter(
                is_global=False,
                domain=domain,
                name=name,
                deleted=False
            )
        else:
            result = cls.objects.filter(
                is_global=True,
                name=name,
                deleted=False
            )

        result = result.values_list('id', flat=True)
        if len(result) == 0:
            return True

        if len(result) == 1:
            return result[0] == backend_id

        return False

    def get_authorized_domain_list(self):
        return (self.mobilebackendinvitation_set.filter(accepted=True)
                .order_by('domain').values_list('domain', flat=True))

    @classmethod
    def get_domain_backends(cls, backend_type, domain, count_only=False, offset=None, limit=None):
        """
        Returns all the backends that the given domain has access to (that is,
        owned backends, shared backends, and global backends).
        """
        domain_owned_backends = models.Q(is_global=False, domain=domain)
        domain_shared_backends = models.Q(
            is_global=False,
            mobilebackendinvitation__domain=domain,
            mobilebackendinvitation__accepted=True
        )
        global_backends = models.Q(is_global=True)

        # The left join to MobileBackendInvitation may cause there to be
        # duplicates here, so we need to call .distinct()
        result = SQLMobileBackend.objects.filter(
            (domain_owned_backends | domain_shared_backends | global_backends),
            deleted=False,
            backend_type=backend_type
        ).distinct()

        if count_only:
            return result.count()

        result = result.order_by('name').values_list('id', flat=True)
        if offset is not None and limit is not None:
            result = result[offset:offset + limit]

        return [cls.load(pk) for pk in result]

    @classmethod
    def get_global_backends_for_this_class(cls, backend_type):
        return cls.objects.filter(
            is_global=True,
            deleted=False,
            backend_type=backend_type,
            hq_api_id=cls.get_api_id()
        ).all()

    @classmethod
    def get_global_backend_ids(cls, backend_type, couch_id=False):
        id_field = 'couch_id' if couch_id else 'id'
        return SQLMobileBackend.active_objects.filter(
            backend_type=backend_type,
            is_global=True
        ).values_list(id_field, flat=True)

    @classmethod
    def get_global_backends(cls, backend_type, count_only=False, offset=None, limit=None):
        result = SQLMobileBackend.objects.filter(
            is_global=True,
            deleted=False,
            backend_type=backend_type
        )

        if count_only:
            return result.count()

        result = result.order_by('name').values_list('id', flat=True)
        if offset is not None and limit is not None:
            result = result[offset:offset + limit]

        return [cls.load(pk) for pk in result]

    @classmethod
    def get_domain_default_backend(cls, backend_type, domain, id_only=False):
        result = SQLMobileBackendMapping.objects.filter(
            is_global=False,
            domain=domain,
            backend_type=backend_type,
            prefix='*'
        ).values_list('backend_id', flat=True)

        if len(result) > 1:
            raise cls.MultipleObjectsReturned(
                "More than one default backend found for backend_type %s, "
                "domain %s" % (backend_type, domain)
            )
        elif len(result) == 1:
            if id_only:
                return result[0]
            else:
                return cls.load(result[0])
        else:
            return None

    @classmethod
    def load_default_backend(cls, backend_type, phone_number, domain=None):
        """
        Chooses the appropriate backend based on the phone number's
        prefix, or returns None if no catch-all backend is configured.

        backend_type - SQLMobileBackend.SMS or SQLMobileBackend.IVR
        phone_number - the phone number
        domain - pass in a domain to choose the default backend from the domain's
                 configured backends, otherwise leave None to choose from the
                 system's configured backends
        """
        backend_map = SQLMobileBackendMapping.get_prefix_to_backend_map(
            backend_type, domain=domain)
        backend_id = backend_map.get_backend_id_by_prefix(phone_number)
        if backend_id:
            return cls.load(backend_id)
        return None

    @classmethod
    def load_default_by_phone_and_domain(cls, backend_type, phone_number, domain=None):
        """
        Get the appropriate outbound backend to communicate with phone_number.

        backend_type - SQLMobileBackend.SMS or SQLMobileBackend.IVR
        phone_number - the phone number
        domain - the domain
        """
        backend = None

        if domain:
            backend = cls.load_default_backend(backend_type, phone_number, domain=domain)

        if not backend:
            backend = cls.load_default_backend(backend_type, phone_number)

        if not backend:
            raise BadSMSConfigException("No suitable backend found for phone "
                                        "number and domain %s, %s" %
                                        (phone_number, domain))

        return backend

    @classmethod
    @quickcache(['hq_api_id', 'inbound_api_key'], timeout=60 * 60)
    def get_backend_info_by_api_key(cls, hq_api_id, inbound_api_key):
        """
        Looks up a backend by inbound_api_key and returns a tuple of
        (domain, couch_id). Including hq_api_id in the filter is an
        implicit way of making sure that the returned backend info belongs
        to a backend of that type.

        (The entire backend is not returned to reduce the amount of data
        needed to be returned by the cache)

        Raises cls.DoesNotExist if not found.
        """
        result = (cls.active_objects
                  .filter(hq_api_id=hq_api_id, inbound_api_key=inbound_api_key)
                  .values_list('domain', 'couch_id'))

        if len(result) == 0:
            raise cls.DoesNotExist

        return result[0]

    @classmethod
    @quickcache(['backend_id', 'is_couch_id'], timeout=60 * 60)
    def get_backend_api_id(cls, backend_id, is_couch_id=False):
        filter_args = {'couch_id': backend_id} if is_couch_id else {'pk': backend_id}
        result = (cls.active_objects
                  .filter(**filter_args)
                  .values_list('hq_api_id', flat=True))

        if len(result) == 0:
            raise cls.DoesNotExist

        return result[0]

    @classmethod
    @quickcache(['backend_id', 'is_couch_id', 'include_deleted'], timeout=5 * 60)
    def load(cls, backend_id, api_id=None, is_couch_id=False, include_deleted=False):
        """
        backend_id - the pk of the SQLMobileBackend to load
        api_id - if you know the hq_api_id of the SQLMobileBackend, pass it
                 here for a faster lookup; otherwise, it will be looked up
                 automatically
        is_couch_id - if True, then backend_id should be the couch_id to use
                   during lookup instead of the postgres model's pk;
                   we have to support both for a little while until all
                   foreign keys are migrated over
        """
        backend_classes = smsutil.get_sms_backend_classes()
        api_id = api_id or cls.get_backend_api_id(backend_id, is_couch_id=is_couch_id)

        if api_id not in backend_classes:
            raise BadSMSConfigException("Unexpected backend api id found '%s' for "
                                        "backend '%s'" % (api_id, backend_id))

        klass = backend_classes[api_id]

        if include_deleted:
            result = klass.objects
        else:
            result = klass.active_objects

        if is_couch_id:
            return result.get(couch_id=backend_id)
        else:
            return result.get(pk=backend_id)

    @classmethod
    def get_backend_from_id_and_api_id_result(cls, result):
        if len(result) > 0:
            return cls.load(result[0]['id'], api_id=result[0]['hq_api_id'])

        return None

    @classmethod
    def get_owned_backend_by_name(cls, backend_type, domain, name):
        name = name.strip().upper()
        result = cls.active_objects.filter(
            is_global=False,
            backend_type=backend_type,
            domain=domain,
            name=name
        ).values('id', 'hq_api_id')
        return cls.get_backend_from_id_and_api_id_result(result)

    @classmethod
    def get_shared_backend_by_name(cls, backend_type, domain, name):
        name = name.strip().upper()
        result = cls.active_objects.filter(
            is_global=False,
            backend_type=backend_type,
            mobilebackendinvitation__domain=domain,
            mobilebackendinvitation__accepted=True,
            name=name
        ).values('id', 'hq_api_id').order_by('domain')
        return cls.get_backend_from_id_and_api_id_result(result)

    @classmethod
    def get_global_backend_by_name(cls, backend_type, name):
        name = name.strip().upper()
        result = cls.active_objects.filter(
            is_global=True,
            backend_type=backend_type,
            name=name
        ).values('id', 'hq_api_id')
        return cls.get_backend_from_id_and_api_id_result(result)

    @classmethod
    def load_by_name(cls, backend_type, domain, name):
        """
        Attempts to load the backend with the given name.
        If no matching backend is found, a BadSMSConfigException is raised.

        backend_type - SQLMobileBackend.SMS or SQLMobileBackend.IVR
        domain - the domain
        name - the name of the backend (corresponding to SQLMobileBackend.name)
        """
        backend = cls.get_owned_backend_by_name(backend_type, domain, name)

        if not backend:
            backend = cls.get_shared_backend_by_name(backend_type, domain, name)

        if not backend:
            backend = cls.get_global_backend_by_name(backend_type, name)

        if not backend:
            raise BadSMSConfigException("Could not find %s backend '%s' from "
                                        "domain '%s'" % (backend_type, name, domain))

        return backend

    @classmethod
    def get_api_id(cls):
        """
        This method should return the backend's api id.
        """
        raise NotImplementedError("Please implement this method")

    @classmethod
    def get_generic_name(cls):
        """
        This method should return a descriptive name for this backend
        (such as "Unicel" or "Tropo"), for use in identifying it to an end user.
        """
        raise NotImplementedError("Please implement this method")

    @classmethod
    def get_form_class(cls):
        """
        This method should return a subclass of corehq.apps.sms.forms.BackendForm
        """
        raise NotImplementedError("Please implement this method")

    @classmethod
    def get_available_extra_fields(cls):
        """
        Should return a list of field names that are the keys in
        the extra_fields dict.
        """
        raise NotImplementedError("Please implement this method")

    @property
    def config(self):
        """
        Returns self.get_extra_fields() converted into a namedtuple so that
        you can reference self.config.gateway_user_id, for example,
        instead of self.get_extra_fields()['gateway_user_id']
        """
        BackendConfig = namedtuple('BackendConfig', self.get_available_extra_fields())
        return BackendConfig(**self.get_extra_fields())

    def get_extra_fields(self):
        result = {field: None for field in self.get_available_extra_fields()}
        result.update(self.extra_fields)
        return result

    def set_extra_fields(self, **kwargs):
        """
        Only updates the fields that are passed as kwargs, and leaves
        the rest untouched.
        """
        result = self.get_extra_fields()
        for k, v in kwargs.items():
            if k not in self.get_available_extra_fields():
                raise Exception("Field %s is not an available extra field for %s"
                    % (k, self.__class__.__name__))
            result[k] = v

        self.extra_fields = result

    def __clear_shared_domain_cache(self, new_domains):
        current_domains = self.mobilebackendinvitation_set.values_list('domain', flat=True)
        # Clear the cache for domains in new_domains or current_domains, but not both
        for domain in set(current_domains) ^ set(new_domains):
            self.domain_is_shared.clear(self, domain)

    def set_shared_domains(self, domains):
        if self.id is None:
            raise Exception("Please call .save() on the backend before "
                "calling set_shared_domains()")
        with transaction.atomic():
            self.__clear_shared_domain_cache(domains)
            self.mobilebackendinvitation_set.all().delete()
            for domain in domains:
                MobileBackendInvitation.objects.create(
                    domain=domain,
                    accepted=True,
                    backend=self,
                )

    def soft_delete(self):
        with transaction.atomic():
            self.deleted = True
            self.__clear_shared_domain_cache([])
            self.mobilebackendinvitation_set.all().delete()
            for mapping in self.sqlmobilebackendmapping_set.all():
                # Delete one at a time so the backend map cache gets cleared
                # for the respective domain(s)
                mapping.delete()
            self.save()

    def __clear_caches(self):
        if self.pk:
            self.load.clear(SQLMobileBackend, self.pk, is_couch_id=False)
            self.get_backend_api_id.clear(SQLMobileBackend, self.pk, is_couch_id=False)

        if self.couch_id:
            self.load.clear(SQLMobileBackend, self.couch_id, is_couch_id=True)
            self.get_backend_api_id.clear(SQLMobileBackend, self.couch_id, is_couch_id=True)

    def save(self, *args, **kwargs):
        self.__clear_caches()
        return super(SQLMobileBackend, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.__clear_caches()
        self.__clear_shared_domain_cache([])
        return super(SQLMobileBackend, self).delete(*args, **kwargs)


class SQLSMSBackend(SQLMobileBackend):

    class Meta(object):
        proxy = True
        app_label = 'sms'

    def get_max_simultaneous_connections(self):
        """
        Return None to ignore.
        Otherwise, return the maximum number of simultaneous connections
        that should be allowed when making requests to the gateway API
        for sending outbound SMS.
        """
        return None

    def get_sms_rate_limit(self):
        """
        Override to use rate limiting. Return None to not use rate limiting,
        otherwise return the maximum number of SMS that should be sent by
        this backend instance in a one minute period.
        """
        return None

    def send(self, msg, *args, **kwargs):
        raise NotImplementedError("Please implement this method.")

    # Override in case backend is fetching gateway fees through provider API
    using_api_to_get_fees = False

    @classmethod
    def get_opt_in_keywords(cls):
        """
        Override to specify a set of opt-in keywords to use for this
        backend type.
        """
        return []

    @classmethod
    def get_pass_through_opt_in_keywords(cls):
        """
        Use this to define opt-in keywords that the gateway counts as opt-in
        keywords but that we don't want to have block normal processing in HQ.

        This is useful when the gateway defines an opt-in keyword like
        YES that is a common reply to SMS survey questions, and we don't
        want users to continuously be getting opt-in replies when
        sending YES.

        When receiving these keywords, HQ will still mark the phone as having
        opted-in in the PhoneBlacklist entry because it's important that the
        opt-in status between the gateway and HQ remain in sync, but after doing
        that, HQ will then process the inbound SMS just as a normal inbound message.
        """
        return []

    @classmethod
    def get_opt_out_keywords(cls):
        """
        Override to specify a set of opt-out keywords to use for this
        backend type.
        """
        return []


class PhoneLoadBalancingMixin(object):
    """
    If you need a backend to balance the outbound SMS load over a set of
    phone numbers, use this mixin. To use it:

    1) Include this mixin in your backend class.
    2) Have the send() method expect an orig_phone_number kwarg, which will
       be the phone number to send from. This parameter is always sent in for
       instances of PhoneLoadBalancingMixin, even if there's just one phone
       number in self.load_balancing_numbers.
    3) Have the backend's form class use the LoadBalancingBackendFormMixin to
       automatically set the load balancing phone numbers in the UI.

    If the backend also uses rate limiting, then each phone number is rate
    limited separately as you would expect.

    (We could also just define these methods on the backend class itself, but
    it's useful in other parts of the framework to check if a backend
    is an instance of this mixin for performing various operations.)
    """

    def get_next_phone_number(self, destination_phone_number):
        if (
            not isinstance(self.load_balancing_numbers, list)
            or len(self.load_balancing_numbers) == 0
        ):
            raise Exception("Expected load_balancing_numbers to not be "
                            "empty for backend %s" % self.pk)

        if len(self.load_balancing_numbers) == 1:
            # If there's just one number, no need to go through the
            # process to figure out which one is next.
            return self.load_balancing_numbers[0]

        hashed_destination_phone_number = hashlib.sha1(destination_phone_number.encode('utf-8')).hexdigest()
        index = int(hashed_destination_phone_number, base=16) % len(self.load_balancing_numbers)
        return self.load_balancing_numbers[index]


class BackendMap(object):

    def __init__(self, catchall_backend_id, backend_map):
        """
        catchall_backend_id - the pk of the backend that is the default if
                              no prefixes match (can be None if there is no
                              catch all)
        backend_map - a dictionary of {prefix: backend pk} which
                      maps a phone prefix to the backend which should be
                      used for that phone prefix
        """
        self.catchall_backend_id = catchall_backend_id
        self.backend_map_dict = backend_map
        self.backend_map_tuples = list(backend_map.items())
        # Sort by length of prefix descending
        self.backend_map_tuples.sort(key=lambda x: len(x[0]), reverse=True)

    def get_backend_id_by_prefix(self, phone_number):
        phone_number = smsutil.strip_plus(phone_number)
        for prefix, backend_id in self.backend_map_tuples:
            if phone_number.startswith(prefix):
                return backend_id
        return self.catchall_backend_id


class SQLMobileBackendMapping(models.Model):
    """
    A SQLMobileBackendMapping instance is used to map SMS or IVR traffic
    to a given backend based on phone prefix.

    The SQLMobileBackendMappings that have is_global set to True are managed
    in CommCareHQ's Admin section for SMS Connectivity and Billing.

    It also possible to create SQLMobileBackendMappings that have is_global_set to False
    in order to define custom rules for how to route outbound SMS traffic for a specific project.
    This is used so infrequently that no CommCareHQ UI exists to manage it, but if
    you need to enable this you can do so using the Django admin. Just create a
    SQLMobileBackendMapping entry with couch_id blank, is_global False, domain equal
    to the domain you wish to apply this for, backend_type SMS, prefix equal to the
    mobile prefix that you want to route outbound SMS traffic for, and then for
    backend choose a backend either in the same project as domain, one that is
    shared with domain, or one that is global.
    """
    class Meta(object):
        db_table = 'messaging_mobilebackendmapping'
        app_label = 'sms'
        unique_together = ('domain', 'backend_type', 'prefix')

    # This column can be left null for new entries. If there aren't any references to it anywhere, it
    # can probably be dropped.
    couch_id = models.CharField(max_length=126, null=True, db_index=True, blank=True)

    # True if this mapping applies globally (system-wide). False if it only applies
    # to a domain
    is_global = models.BooleanField(default=False)

    # The domain for which this mapping is valid; ignored if is_global is True
    domain = models.CharField(max_length=126, null=True)

    # Specifies whether this mapping is valid for SMS or IVR backends
    backend_type = models.CharField(max_length=3, choices=SQLMobileBackend.TYPE_CHOICES)

    # The phone prefix, or '*' for catch-all
    prefix = models.CharField(max_length=25)

    # The backend to use for the given phone prefix
    backend = models.ForeignKey('SQLMobileBackend', on_delete=models.CASCADE)

    @classmethod
    def __set_default_domain_backend(cls, domain, backend_type, backend=None):
        fields = dict(
            is_global=False,
            domain=domain,
            backend_type=backend_type,
            prefix='*'
        )

        obj = None
        try:
            # We can't use get_or_create because backend is a
            # required field
            obj = cls.objects.get(**fields)
        except cls.DoesNotExist:
            pass

        if not backend:
            if obj:
                obj.delete()
            return

        if not obj:
            obj = cls(**fields)

        obj.backend = backend
        obj.save()

    @classmethod
    def set_default_domain_backend(cls, domain, backend, backend_type=SQLMobileBackend.SMS):
        cls.__set_default_domain_backend(domain, backend_type, backend=backend)

    @classmethod
    def unset_default_domain_backend(cls, domain, backend_type=SQLMobileBackend.SMS):
        cls.__set_default_domain_backend(domain, backend_type)

    @classmethod
    @quickcache(['backend_type', 'domain'], timeout=5 * 60)
    def get_prefix_to_backend_map(cls, backend_type, domain=None):
        """
        backend_type - SQLMobileBackend.SMS or SQLMobileBackend.IVR
        domain - the domain for which to retrieve the backend map, otherwise if left None
                 the global backend map will be returned.
        Returns a BackendMap
        """
        if domain:
            filter_args = {'backend_type': backend_type, 'is_global': False, 'domain': domain}
        else:
            filter_args = {'backend_type': backend_type, 'is_global': True}

        catchall_backend_id = None
        backend_map = {}
        for instance in cls.objects.filter(**filter_args):
            if instance.prefix == '*':
                catchall_backend_id = instance.backend_id
            else:
                backend_map[instance.prefix] = instance.backend_id

        return BackendMap(catchall_backend_id, backend_map)

    def __clear_prefix_to_backend_map_cache(self):
        self.get_prefix_to_backend_map.clear(self.__class__, self.backend_type, domain=self.domain)

    def save(self, *args, **kwargs):
        self.__clear_prefix_to_backend_map_cache()
        return super(SQLMobileBackendMapping, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.__clear_prefix_to_backend_map_cache()
        return super(SQLMobileBackendMapping, self).delete(*args, **kwargs)


class MobileBackendInvitation(models.Model):

    class Meta(object):
        db_table = 'messaging_mobilebackendinvitation'
        app_label = 'sms'
        unique_together = ('backend', 'domain')

    # The domain that is being invited to share another domain's backend
    domain = models.CharField(max_length=126, null=True, db_index=True)

    # The backend that is being shared
    backend = models.ForeignKey('SQLMobileBackend', on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)


class MigrationStatus(models.Model):
    """
    A model to keep track of whether certain messaging migrations have
    been run yet or not.
    """

    MIGRATION_BACKEND = 'backend'
    MIGRATION_BACKEND_MAP = 'backend_map'
    MIGRATION_DOMAIN_DEFAULT_BACKEND = 'domain_default_backend'
    MIGRATION_LOGS = 'logs'
    MIGRATION_PHONE_NUMBERS = 'phone_numbers'
    MIGRATION_KEYWORDS = 'keywords'

    class Meta(object):
        db_table = 'messaging_migrationstatus'
        app_label = "sms"

    # The name of the migration (one of the MIGRATION_* constants above)
    name = models.CharField(max_length=126)

    # The timestamp that the migration was run
    timestamp = models.DateTimeField(null=True)

    @classmethod
    def set_migration_completed(cls, name):
        obj, created = cls.objects.get_or_create(name=name)
        obj.timestamp = datetime.utcnow()
        obj.save()

    @classmethod
    def has_migration_completed(cls, name):
        try:
            cls.objects.get(name=name)
            return True
        except cls.DoesNotExist:
            return False


class Keyword(UUIDGeneratorMixin, models.Model):
    """
    A Keyword allows a project to define actions to be taken when a contact
    in the project sends an inbound SMS starting with a certain word.
    """
    UUIDS_TO_GENERATE = ['couch_id']

    class Meta(object):
        index_together = (
            ('domain', 'keyword')
        )

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    domain = models.CharField(max_length=126, db_index=True)

    # The word which is used to invoke this Keyword's KeywordActions
    keyword = models.CharField(max_length=126)
    description = models.TextField(null=True)

    # When specified, this is the delimiter that is used in the structured SMS format.
    # If None, the delimiter is any consecutive white space.
    # This is ignored unless this Keyword is describing a structured SMS
    # (i.e., it has a KeywordAction with action equal to ACTION_STRUCTURED_SMS)
    delimiter = models.CharField(max_length=126, null=True)

    # If a SQLXFormsSession (i.e., an sms survey) is open for a contact when they invoke this
    # Keyword, override_open_sessions tells what to do with it. If True, the SQLXFormsSession
    # will be closed and this Keyword will be invoked. If False, this Keyword will be
    # skipped and the form session handler will count the text as the next
    # answer in the open survey.
    override_open_sessions = models.BooleanField(null=True)

    # List of doc types representing the only types of contacts who should be
    # able to invoke this keyword. Empty list means anyone can invoke.
    # Example: ['CommCareUser', 'CommCareCase']
    initiator_doc_type_filter = jsonfield.JSONField(default=list)

    last_modified = models.DateTimeField(auto_now=True)

    # For use with linked domains - the upstream keyword
    upstream_id = models.CharField(max_length=126, null=True)

    def is_structured_sms(self):
        return self.keywordaction_set.filter(action=KeywordAction.ACTION_STRUCTURED_SMS).count() > 0

    @property
    def get_id(self):
        return self.couch_id

    @classmethod
    def get_keyword(cls, domain, keyword):
        try:
            return cls.objects.get(domain=domain, keyword__iexact=keyword)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_by_domain(cls, domain, limit=None, skip=None):
        qs = Keyword.objects.filter(domain=domain).order_by('keyword')

        if skip is not None:
            qs = qs[skip:]

        if limit is not None:
            qs = qs[:limit]

        return qs

    def save(self, *args, **kwargs):
        self.clear_caches()
        return super(Keyword, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clear_caches()
        return super(Keyword, self).delete(*args, **kwargs)

    def clear_caches(self):
        self.domain_has_keywords.clear(Keyword, self.domain)

    @classmethod
    @quickcache(['domain'], timeout=60 * 60)
    def domain_has_keywords(cls, domain):
        return cls.get_by_domain(domain).count() > 0


class KeywordAction(models.Model):
    """
    When a Keyword is invoked, its KeywordActions are processed. A KeywordAction
    defines the action to take (which could be sending an SMS, or starting an
    SMS survey, for example) and the recipient of that action.
    """

    class InvalidModelStateException(Exception):
        pass

    # Send an SMS
    ACTION_SMS = "sms"

    # Start an SMS Survey
    ACTION_SMS_SURVEY = "survey"

    # Process the text as structured SMS. The expected format of the structured
    # SMS is described using the fields on this object.
    ACTION_STRUCTURED_SMS = "structured_sms"

    # The recipient of this action is the contact who invoked the keyword.
    RECIPIENT_SENDER = "SENDER"

    # The recipient of this action is the owner of the case contact who invoked
    # the keyword.
    RECIPIENT_OWNER = "OWNER"

    # The recipient of this action is a user group (Group) with id given by
    # recipient_id.
    RECIPIENT_USER_GROUP = "USER_GROUP"

    # The Keyword that this KeywordAction belongs to
    keyword = models.ForeignKey('Keyword', on_delete=models.CASCADE)

    # One of the ACTION_* constants representing the action to take
    action = models.CharField(max_length=126)

    # One of the RECIPIENT_* constants representing the recipient of this action
    recipient = models.CharField(max_length=126)

    # Represents the id of the recipient, when necessary
    recipient_id = models.CharField(max_length=126, null=True)

    # Only used for action == ACTION_SMS
    message_content = models.TextField(null=True)

    # Only used for action in [ACTION_SMS_SURVEY, ACTION_STRUCTURED_SMS]
    # The form unique id of the form to use as a survey when processing this action.
    app_id = models.CharField(max_length=126, null=True)
    form_unique_id = models.CharField(max_length=126, null=True)

    # Only used for action == ACTION_STRUCTURED_SMS
    # Set to True if the expected structured SMS format should name the values
    # being passed. For example the format "register name=joe age=20" would set
    # this to True, while the format "register joe 20" would set it to False.
    use_named_args = models.BooleanField(null=True)

    # Only used for action == ACTION_STRUCTURED_SMS
    # When use_named_args is True, this is a dictionary of {arg name (caps) : form question xpath}
    # So for example, in structured SMS "register name=joe age=20", the expected
    # arg names are NAME and AGE. They would be keys in this dictionary and their
    # corresponding values would be the corresponding question xpaths in the form
    # referenced by form_unique_id, for example /data/name and /data/age.
    named_args = jsonfield.JSONField(default=dict)

    # Only used for action == ACTION_STRUCTURED_SMS
    # When use_named_args is True, this is the separator to be used between arg name
    # and value in the structured SMS.
    # So for example, in structured SMS "register name=joe age=20", the separator
    # is "=".
    # This can be None in which case there is no separator (i.e., "report a100 b200")
    named_args_separator = models.CharField(max_length=126, null=True)

    def save(self, *args, **kwargs):
        if self.recipient == self.RECIPIENT_USER_GROUP and not self.recipient_id:
            raise self.InvalidModelStateException("Expected a value for recipient_id")

        if self.action == self.ACTION_SMS and not self.message_content:
            raise self.InvalidModelStateException("Expected a value for message_content")

        if self.action in [self.ACTION_SMS_SURVEY, self.ACTION_STRUCTURED_SMS]:
            if not self.app_id:
                raise self.InvalidModelStateException("Expected a value for app_id")
            if not self.form_unique_id:
                raise self.InvalidModelStateException("Expected a value for form_unique_id")

        super(KeywordAction, self).save(*args, **kwargs)


class DailyOutboundSMSLimitReached(models.Model):
    """
    Represents an instance of a domain reaching its daily outbound
    SMS limit on a specific date.
    """

    # The domain name that reached its daily outbound SMS limit as defined
    # on Domain.get_daily_outbound_sms_limit(). This can be empty string if
    # we reached the limit for outbound SMS not tied to a domain.
    domain = models.CharField(max_length=126)

    # The UTC date representing the 24-hour window in which the limit was reached
    date = models.DateField()

    class Meta(object):
        unique_together = (
            ('domain', 'date')
        )

    @classmethod
    def create_for_domain_and_date(cls, domain, date):
        # Using get_or_create here would be less efficient since
        # it would require two queries to be issued, and still would
        # require use of a CriticalSection to prevent IntegrityErrors.
        try:
            cls.objects.create(domain=domain, date=date)
        except IntegrityError:
            pass


class Email(models.Model):
    """
    Represents an email that is associated with a messaging subevent.
    """

    domain = models.CharField(max_length=126, db_index=True)
    date = models.DateTimeField(db_index=True)
    date_modified = models.DateTimeField(null=True, db_index=True, auto_now=True)
    couch_recipient_doc_type = models.CharField(max_length=126, db_index=True)
    couch_recipient = models.CharField(max_length=126, db_index=True)

    # The MessagingSubEvent that this email is tied to
    messaging_subevent = models.ForeignKey('sms.MessagingSubEvent', null=True, on_delete=models.PROTECT)

    # Email details
    recipient_address = models.CharField(max_length=255, db_index=True)
    subject = models.TextField(null=True)
    body = models.TextField(null=True)
    html_body = models.TextField(null=True)

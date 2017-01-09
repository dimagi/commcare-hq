#!/usr/bin/env python
import base64
import jsonfield
import uuid
from dimagi.ext.couchdbkit import *

from datetime import datetime, timedelta
from django.db import models, transaction
from django.http import Http404
from collections import namedtuple
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Form
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.mixin import UUIDGeneratorMixin
from corehq.apps.users.models import CouchUser
from corehq.apps.sms.mixin import (CommCareMobileContactMixin,
    InvalidFormatException,
    apply_leniency, BadSMSConfigException)
from corehq.apps.sms import util as smsutil
from corehq.apps.sms.messages import (MSG_MOBILE_WORKER_INVITATION_START,
    MSG_MOBILE_WORKER_ANDROID_INVITATION, MSG_MOBILE_WORKER_JAVA_INVITATION,
    MSG_REGISTRATION_INSTALL_COMMCARE, get_message)
from corehq.const import GOOGLE_PLAY_STORE_COMMCARE_URL
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.load_balance import load_balance
from django.utils.translation import ugettext_noop, ugettext_lazy


INCOMING = "I"
OUTGOING = "O"

CALLBACK_PENDING = "PENDING"
CALLBACK_RECEIVED = "RECEIVED"
CALLBACK_MISSED = "MISSED"

FORWARD_ALL = "ALL"
FORWARD_BY_KEYWORD = "KEYWORD"
FORWARDING_CHOICES = [FORWARD_ALL, FORWARD_BY_KEYWORD]

WORKFLOW_CALLBACK = "CALLBACK"
WORKFLOW_REMINDER = "REMINDER"
WORKFLOW_KEYWORD = "KEYWORD"
WORKFLOW_FORWARD = "FORWARD"
WORKFLOW_BROADCAST = "BROADCAST"
WORKFLOW_PERFORMANCE = "PERFORMANCE"
WORKFLOW_DEFAULT = 'default'

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))


class Log(models.Model):

    class Meta:
        abstract = True
        app_label = "sms"

    domain = models.CharField(max_length=126, null=True, db_index=True)
    date = models.DateTimeField(null=True, db_index=True)
    couch_recipient_doc_type = models.CharField(max_length=126, null=True, db_index=True)
    couch_recipient = models.CharField(max_length=126, null=True, db_index=True)
    phone_number = models.CharField(max_length=126, null=True, db_index=True)
    direction = models.CharField(max_length=1, null=True)
    error = models.NullBooleanField(default=False)
    system_error_message = models.TextField(null=True)
    system_phone_number = models.CharField(max_length=126, null=True)
    backend_api = models.CharField(max_length=126, null=True)
    backend_id = models.CharField(max_length=126, null=True)
    billed = models.NullBooleanField(default=False)

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
            return CaseAccessors(self.domain).get_case(self.couch_recipient)
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

    ERROR_MESSAGES = {
        ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS:
            ugettext_noop('Gateway error.'),
        ERROR_MESSAGE_IS_STALE:
            ugettext_noop('Message is stale and will not be processed.'),
        ERROR_INVALID_DIRECTION:
            ugettext_noop('Unknown message direction.'),
        ERROR_PHONE_NUMBER_OPTED_OUT:
            ugettext_noop('Phone number has opted out of receiving SMS.'),
        ERROR_INVALID_DESTINATION_NUMBER:
            ugettext_noop("The gateway can't reach the destination number."),
        ERROR_MESSAGE_TOO_LONG:
            ugettext_noop("The gateway could not process the message because it was too long."),
        ERROR_CONTACT_IS_INACTIVE:
            ugettext_noop("The recipient has been deactivated."),
    }

    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    text = models.TextField(null=True)

    # In cases where decoding must occur, this is the raw text received
    # from the gateway
    raw_text = models.TextField(null=True)
    datetime_to_process = models.DateTimeField(null=True, db_index=True)
    processed = models.NullBooleanField(default=True, db_index=True)
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
    ignore_opt_out = models.NullBooleanField(default=False)

    # This is the unique message id that the gateway uses to track this
    # message, if applicable.
    backend_message_id = models.CharField(max_length=126, null=True)

    # For outgoing sms only: if this sms was sent from a chat window,
    # the _id of the CouchUser who sent this sms; otherwise None
    chat_user_id = models.CharField(max_length=126, null=True)

    # True if this was an inbound message that was an
    # invalid response to a survey question
    invalid_survey_response = models.NullBooleanField(default=False)

    """ Custom properties. For the initial migration, it makes it easier
    to put these here. Eventually they should be moved to a separate table. """
    fri_message_bank_lookup_completed = models.NullBooleanField(default=False)
    fri_message_bank_message_id = models.CharField(max_length=126, null=True)
    fri_id = models.CharField(max_length=126, null=True)
    fri_risk_profile = models.CharField(max_length=1, null=True)

    class Meta:
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


class SMS(SMSBase):

    def to_json(self):
        from corehq.apps.sms.serializers import SMSSerializer
        data = SMSSerializer(self).data
        return data

    def publish_change(self):
        from corehq.apps.sms.tasks import publish_sms_change
        publish_sms_change.delay(self)


class QueuedSMS(SMSBase):

    class Meta:
        db_table = 'sms_queued'

    @classmethod
    def get_queued_sms(cls):
        return cls.objects.filter(
            datetime_to_process__lte=datetime.utcnow(),
        )


class SQLLastReadMessage(UUIDGeneratorMixin, models.Model):

    class Meta:
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

    class Meta:
        app_label = 'sms'
        index_together = [
            ['domain', 'date'],
        ]

    STATUS_CHOICES = (
        (CALLBACK_PENDING, ugettext_lazy("Pending")),
        (CALLBACK_RECEIVED, ugettext_lazy("Received")),
        (CALLBACK_MISSED, ugettext_lazy("Missed")),
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


class ForwardingRule(Document):
    domain = StringProperty()
    forward_type = StringProperty(choices=FORWARDING_CHOICES)
    keyword = StringProperty()
    backend_id = StringProperty() # id of MobileBackend which will be used to do the forwarding
    
    def retire(self):
        self.doc_type += "-Deleted"
        self.save()


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

    class Meta:
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
        try:
            phone_obj = cls.get_by_phone_number(phone_number)
            if phone_obj.can_opt_in:
                phone_obj.domain = domain
                phone_obj.send_sms = True
                phone_obj.last_sms_opt_in_timestamp = datetime.utcnow()
                phone_obj.save()
                return True
        except cls.DoesNotExist:
            pass
        return False

    @classmethod
    def opt_out_sms(cls, phone_number, domain=None):
        """
        Opts a phone number out from receiving SMS.
        Returns True if the number was actually opted-out, False if not.
        """
        phone_obj = cls.get_or_create(phone_number)[0]
        if phone_obj:
            phone_obj.domain = domain
            phone_obj.send_sms = False
            phone_obj.last_sms_opt_out_timestamp = datetime.utcnow()
            phone_obj.save()
            return True
        return False


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
    verified = models.NullBooleanField(default=False)
    contact_last_modified = models.DateTimeField(null=True)

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
        backend_id = self.backend_id.strip() if isinstance(self.backend_id, basestring) else None
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
            from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
            return CaseAccessors(self.domain).get_case(self.owner_id)
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
        # Try to look up the verified number entry directly
        v = cls.by_phone(phone_number)

        # If not found, try to see if any number in the database is a substring
        # of the number given to us. This can happen if the telco prepends some
        # international digits, such as 011...
        if v is None:
            v = cls.by_phone(phone_number[1:])
        if v is None:
            v = cls.by_phone(phone_number[2:])
        if v is None:
            v = cls.by_phone(phone_number[3:])

        # If still not found, try to match only the last digits of numbers in
        # the database. This can happen if the telco removes the country code
        # in the caller id.
        if v is None:
            v = cls.by_suffix(phone_number)

        return v

    @classmethod
    def by_couch_id(cls, couch_id):
        try:
            return cls.objects.get(couch_id=couch_id)
        except cls.DoesNotExist:
            return None

    @classmethod
    def by_phone(cls, phone_number, include_pending=False):
        result = cls._by_phone(apply_leniency(phone_number))
        return cls._filter_pending(result, include_pending)

    @classmethod
    def by_suffix(cls, phone_number, include_pending=False):
        """
        Used to lookup a PhoneNumber, trying to exclude country code digits.
        """
        result = cls._by_suffix(apply_leniency(phone_number))
        return cls._filter_pending(result, include_pending)

    @classmethod
    @quickcache(['phone_number'], timeout=60 * 60)
    def _by_phone(cls, phone_number):
        try:
            return cls.objects.get(phone_number=phone_number)
        except cls.DoesNotExist:
            return None

    @classmethod
    def _by_suffix(cls, phone_number):
        # Decided not to cache this method since in order to clear the cache
        # we'd have to clear using all suffixes of a number (which would involve
        # up to ~10 cache clear calls on each save). Since this method is used so
        # infrequently, it's better to not cache vs. clear so many keys on each
        # save. Once all of our IVR gateways provide reliable caller id info,
        # we can also remove this method.
        try:
            return cls.objects.get(phone_number__endswith=phone_number)
        except cls.DoesNotExist:
            return None
        except cls.MultipleObjectsReturned:
            return None

    @classmethod
    def _filter_pending(cls, v, include_pending):
        if v:
            if include_pending:
                return v
            elif v.verified:
                return v

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
        return cls.objects.filter(owner_id=owner_id)

    @classmethod
    def _clear_quickcaches(cls, owner_id, phone_number, old_owner_id=None, old_phone_number=None):
        cls.by_owner_id.clear(cls, owner_id)

        if old_owner_id and old_owner_id != owner_id:
            cls.by_owner_id.clear(cls, old_owner_id)

        cls._by_phone.clear(cls, phone_number)

        if old_phone_number and old_phone_number != phone_number:
            cls._by_phone.clear(cls, old_phone_number)

    def _clear_caches(self):
        self._clear_quickcaches(
            self.owner_id,
            self.phone_number,
            old_owner_id=self._old_owner_id,
            old_phone_number=self._old_phone_number
        )

    def save(self, *args, **kwargs):
        self._clear_caches()
        self._old_phone_number = self.phone_number
        self._old_owner_id = self.owner_id
        return super(PhoneNumber, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._clear_caches()
        return super(PhoneNumber, self).delete(*args, **kwargs)


class MessagingStatusMixin(object):

    def refresh(self):
        return self.__class__.objects.get(pk=self.pk)

    def error(self, error_code, additional_error_text=None):
        self.status = MessagingEvent.STATUS_ERROR
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

    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, ugettext_noop('In Progress')),
        (STATUS_COMPLETED, ugettext_noop('Completed')),
        (STATUS_NOT_COMPLETED, ugettext_noop('Not Completed')),
        (STATUS_ERROR, ugettext_noop('Error')),
    )

    SOURCE_BROADCAST = 'BRD'
    SOURCE_KEYWORD = 'KWD'
    SOURCE_REMINDER = 'RMD'
    SOURCE_UNRECOGNIZED = 'UNR'
    SOURCE_FORWARDED = 'FWD'
    SOURCE_OTHER = 'OTH'

    SOURCE_CHOICES = (
        (SOURCE_BROADCAST, ugettext_noop('Broadcast')),
        (SOURCE_KEYWORD, ugettext_noop('Keyword')),
        (SOURCE_REMINDER, ugettext_noop('Reminder')),
        (SOURCE_UNRECOGNIZED, ugettext_noop('Unrecognized')),
        (SOURCE_FORWARDED, ugettext_noop('Forwarded Message')),
        (SOURCE_OTHER, ugettext_noop('Other')),
    )

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

    CONTENT_CHOICES = (
        (CONTENT_NONE, ugettext_noop('None')),
        (CONTENT_SMS, ugettext_noop('SMS Message')),
        (CONTENT_SMS_CALLBACK, ugettext_noop('SMS Expecting Callback')),
        (CONTENT_SMS_SURVEY, ugettext_noop('SMS Survey')),
        (CONTENT_IVR_SURVEY, ugettext_noop('IVR Survey')),
        (CONTENT_PHONE_VERIFICATION, ugettext_noop('Phone Verification')),
        (CONTENT_ADHOC_SMS, ugettext_noop('Manually Sent Message')),
        (CONTENT_API_SMS, ugettext_noop('Message Sent Via API')),
        (CONTENT_CHAT_SMS, ugettext_noop('Message Sent Via Chat')),
        (CONTENT_EMAIL, ugettext_noop('Email')),
    )

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
        (RECIPIENT_CASE, ugettext_noop('Case')),
        (RECIPIENT_MOBILE_WORKER, ugettext_noop('Mobile Worker')),
        (RECIPIENT_WEB_USER, ugettext_noop('Web User')),
        (RECIPIENT_USER_GROUP, ugettext_noop('User Group')),
        (RECIPIENT_CASE_GROUP, ugettext_noop('Case Group')),
        (RECIPIENT_VARIOUS, ugettext_noop('Multiple Recipients')),
        (RECIPIENT_LOCATION, ugettext_noop('Location')),
        (RECIPIENT_LOCATION_PLUS_DESCENDANTS,
            ugettext_noop('Location (including child locations)')),
        (RECIPIENT_VARIOUS_LOCATIONS, ugettext_noop('Multiple Locations')),
        (RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS,
            ugettext_noop('Multiple Locations (including child locations)')),
        (RECIPIENT_UNKNOWN, ugettext_noop('Unknown Contact')),
    )

    ERROR_NO_RECIPIENT = 'NO_RECIPIENT'
    ERROR_CANNOT_RENDER_MESSAGE = 'CANNOT_RENDER_MESSAGE'
    ERROR_UNSUPPORTED_COUNTRY = 'UNSUPPORTED_COUNTRY'
    ERROR_NO_PHONE_NUMBER = 'NO_PHONE_NUMBER'
    ERROR_NO_TWO_WAY_PHONE_NUMBER = 'NO_TWO_WAY_PHONE_NUMBER'
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
    ERROR_GATEWAY_ERROR = 'GATEWAY_ERROR'
    ERROR_NO_SUITABLE_GATEWAY = 'NO_SUITABLE_GATEWAY'
    ERROR_GATEWAY_NOT_FOUND = 'GATEWAY_NOT_FOUND'
    ERROR_NO_EMAIL_ADDRESS = 'NO_EMAIL_ADDRESS'
    ERROR_TRIAL_EMAIL_LIMIT_REACHED = 'TRIAL_EMAIL_LIMIT_REACHED'

    ERROR_MESSAGES = {
        ERROR_NO_RECIPIENT:
            ugettext_noop('No recipient'),
        ERROR_CANNOT_RENDER_MESSAGE:
            ugettext_noop('Error rendering message; please check syntax.'),
        ERROR_UNSUPPORTED_COUNTRY:
            ugettext_noop('Gateway does not support the destination country.'),
        ERROR_NO_PHONE_NUMBER:
            ugettext_noop('Contact has no phone number.'),
        ERROR_NO_TWO_WAY_PHONE_NUMBER:
            ugettext_noop('Contact has no two-way phone number.'),
        ERROR_INVALID_CUSTOM_CONTENT_HANDLER:
            ugettext_noop('Invalid custom content handler.'),
        ERROR_CANNOT_LOAD_CUSTOM_CONTENT_HANDLER:
            ugettext_noop('Cannot load custom content handler.'),
        ERROR_CANNOT_FIND_FORM:
            ugettext_noop('Cannot find form.'),
        ERROR_FORM_HAS_NO_QUESTIONS:
            ugettext_noop('No questions were available in the form. Please '
                'check that the form has questions and that display conditions '
                'are not preventing questions from being asked.'),
        ERROR_CASE_EXTERNAL_ID_NOT_FOUND:
            ugettext_noop('The case with the given external ID was not found.'),
        ERROR_MULTIPLE_CASES_WITH_EXTERNAL_ID_FOUND:
            ugettext_noop('Multiple cases were found with the given external ID.'),
        ERROR_NO_CASE_GIVEN:
            ugettext_noop('The form requires a case but no case was provided.'),
        ERROR_NO_EXTERNAL_ID_GIVEN:
            ugettext_noop('No external ID given; please include case external ID after keyword.'),
        ERROR_COULD_NOT_PROCESS_STRUCTURED_SMS:
            ugettext_noop('Error processing structured SMS.'),
        ERROR_SUBEVENT_ERROR:
            ugettext_noop('View details for more information.'),
        ERROR_TOUCHFORMS_ERROR:
            ugettext_noop('An error occurred in the formplayer service.'),
        ERROR_INTERNAL_SERVER_ERROR:
            ugettext_noop('Internal Server Error'),
        ERROR_GATEWAY_ERROR:
            ugettext_noop('Gateway error.'),
        ERROR_NO_SUITABLE_GATEWAY:
            ugettext_noop('No suitable gateway could be found.'),
        ERROR_GATEWAY_NOT_FOUND:
            ugettext_noop('Gateway could not be found.'),
        ERROR_NO_EMAIL_ADDRESS:
            ugettext_noop('Recipient has no email address.'),
        ERROR_TRIAL_EMAIL_LIMIT_REACHED:
            ugettext_noop("Cannot send any more reminder emails. The limit for "
                "sending reminder emails on a Trial plan has been reached."),
    }

    domain = models.CharField(max_length=126, null=False, db_index=True)
    date = models.DateTimeField(null=False, db_index=True)
    source = models.CharField(max_length=3, choices=SOURCE_CHOICES, null=False)
    source_id = models.CharField(max_length=126, null=True)
    content_type = models.CharField(max_length=3, choices=CONTENT_CHOICES, null=False)

    # Only used when content_type is CONTENT_SMS_SURVEY or CONTENT_IVR_SURVEY
    # This is redundantly stored here (as well as the subevent) so that it
    # doesn't have to be looked up for reporting.
    form_unique_id = models.CharField(max_length=126, null=True)
    form_name = models.TextField(null=True)

    # If any of the MessagingSubEvent status's are STATUS_ERROR, this is STATUS_ERROR
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, null=False)
    error_code = models.CharField(max_length=126, null=True)
    additional_error_text = models.TextField(null=True)
    recipient_type = models.CharField(max_length=3, choices=RECIPIENT_CHOICES, null=True, db_index=True)
    recipient_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        app_label = 'sms'

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

    def create_subevent(self, reminder_definition, reminder, recipient):
        recipient_type = MessagingEvent.get_recipient_type(recipient)
        content_type, form_unique_id, form_name = self.get_content_info_from_reminder(
            reminder_definition, reminder, parent=self)

        obj = MessagingSubEvent.objects.create(
            parent=self,
            date=datetime.utcnow(),
            recipient_type=recipient_type,
            recipient_id=recipient.get_id if recipient_type else None,
            content_type=content_type,
            form_unique_id=form_unique_id,
            form_name=form_name,
            case_id=reminder.case_id,
            status=MessagingEvent.STATUS_IN_PROGRESS,
        )
        return obj

    def create_ivr_subevent(self, recipient, form_unique_id, case_id=None):
        recipient_type = MessagingEvent.get_recipient_type(recipient)
        obj = MessagingSubEvent.objects.create(
            parent=self,
            date=datetime.utcnow(),
            recipient_type=recipient_type,
            recipient_id=recipient.get_id if recipient_type else None,
            content_type=MessagingEvent.CONTENT_IVR_SURVEY,
            form_unique_id=form_unique_id,
            form_name=MessagingEvent.get_form_name_or_none(form_unique_id),
            case_id=case_id,
            status=MessagingEvent.STATUS_IN_PROGRESS,
        )
        return obj

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
            date=datetime.utcnow(),
            recipient_type=self.recipient_type,
            recipient_id=self.recipient_id,
            content_type=MessagingEvent.CONTENT_SMS_SURVEY,
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
    def get_source_from_reminder(cls, reminder_definition):
        from corehq.apps.reminders.models import (REMINDER_TYPE_ONE_TIME,
            REMINDER_TYPE_DEFAULT)

        default = (cls.SOURCE_OTHER, None)
        return {
            REMINDER_TYPE_ONE_TIME:
                (cls.SOURCE_BROADCAST, reminder_definition.get_id),
            REMINDER_TYPE_DEFAULT:
                (cls.SOURCE_REMINDER, reminder_definition.get_id),
        }.get(reminder_definition.reminder_type, default)

    @classmethod
    def get_form_name_or_none(cls, form_unique_id):
        try:
            form = Form.get_form(form_unique_id)
            return form.full_path_name
        except:
            return None

    @classmethod
    def get_content_info_from_reminder(cls, reminder_definition, reminder, parent=None):
        from corehq.apps.reminders.models import (METHOD_SMS, METHOD_SMS_CALLBACK,
            METHOD_SMS_SURVEY, METHOD_IVR_SURVEY, METHOD_EMAIL)
        content_type = {
            METHOD_SMS: cls.CONTENT_SMS,
            METHOD_SMS_CALLBACK: cls.CONTENT_SMS_CALLBACK,
            METHOD_SMS_SURVEY: cls.CONTENT_SMS_SURVEY,
            METHOD_IVR_SURVEY: cls.CONTENT_IVR_SURVEY,
            METHOD_EMAIL: cls.CONTENT_EMAIL,
        }.get(reminder_definition.method, cls.CONTENT_SMS)

        form_unique_id = reminder.current_event.form_unique_id
        if parent and parent.form_unique_id == form_unique_id:
            form_name = parent.form_name
        else:
            form_name = (cls.get_form_name_or_none(form_unique_id)
                if form_unique_id else None)

        return (content_type, form_unique_id, form_name)

    @classmethod
    def get_content_info_from_keyword(cls, keyword):
        content_type = cls.CONTENT_NONE
        form_unique_id = None
        form_name = None

        for action in keyword.keywordaction_set.all():
            if action.recipient == KeywordAction.RECIPIENT_SENDER:
                if action.action in (KeywordAction.ACTION_SMS_SURVEY, KeywordAction.ACTION_STRUCTURED_SMS):
                    content_type = cls.CONTENT_SMS_SURVEY
                    form_unique_id = action.form_unique_id
                    form_name = cls.get_form_name_or_none(action.form_unique_id)
                elif action.action == KeywordAction.ACTION_SMS:
                    content_type = cls.CONTENT_SMS

        return (content_type, form_unique_id, form_name)

    @classmethod
    def create_from_reminder(cls, reminder_definition, reminder, recipient=None):
        if reminder_definition.messaging_event_id:
            return cls.objects.get(pk=reminder_definition.messaging_event_id)

        source, source_id = cls.get_source_from_reminder(reminder_definition)
        content_type, form_unique_id, form_name = cls.get_content_info_from_reminder(
            reminder_definition, reminder)

        if recipient and reminder_definition.recipient_is_list_of_locations(recipient):
            if len(recipient) == 1:
                recipient_type = (cls.RECIPIENT_LOCATION_PLUS_DESCENDANTS
                                  if reminder_definition.include_child_locations
                                  else cls.RECIPIENT_LOCATION)
                recipient_id = recipient[0].location_id
            elif len(recipient) > 1:
                recipient_type = (cls.RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS
                                  if reminder_definition.include_child_locations
                                  else cls.RECIPIENT_VARIOUS_LOCATIONS)
                recipient_id = None
            else:
                # len(recipient) should never be 0 when we invoke this method,
                # but catching this situation here just in case
                recipient_type = cls.RECIPIENT_UNKNOWN
                recipient_id = None
        elif isinstance(recipient, list):
            recipient_type = cls.RECIPIENT_VARIOUS
            recipient_id = None
        elif recipient is None:
            recipient_type = cls.RECIPIENT_UNKNOWN
            recipient_id = None
        else:
            recipient_type = cls.get_recipient_type(recipient)
            recipient_id = recipient.get_id if recipient_type else None

        return cls.objects.create(
            domain=reminder_definition.domain,
            date=datetime.utcnow(),
            source=source,
            source_id=source_id,
            content_type=content_type,
            form_unique_id=form_unique_id,
            form_name=form_name,
            status=cls.STATUS_IN_PROGRESS,
            recipient_type=recipient_type,
            recipient_id=recipient_id
        )

    @classmethod
    def create_from_keyword(cls, keyword, contact):
        """
        keyword - the keyword object
        contact - the person who initiated the keyword
        """
        content_type, form_unique_id, form_name = cls.get_content_info_from_keyword(
            keyword)
        recipient_type = cls.get_recipient_type(contact)

        return cls.objects.create(
            domain=keyword.domain,
            date=datetime.utcnow(),
            source=cls.SOURCE_KEYWORD,
            source_id=keyword.couch_id,
            content_type=content_type,
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


class MessagingSubEvent(models.Model, MessagingStatusMixin):
    """
    Used to track the status of a MessagingEvent for each of its recipients.
    """
    RECIPIENT_CHOICES = (
        (MessagingEvent.RECIPIENT_CASE, ugettext_noop('Case')),
        (MessagingEvent.RECIPIENT_MOBILE_WORKER, ugettext_noop('Mobile Worker')),
        (MessagingEvent.RECIPIENT_WEB_USER, ugettext_noop('Web User')),
    )

    parent = models.ForeignKey('MessagingEvent', on_delete=models.CASCADE)
    date = models.DateTimeField(null=False, db_index=True)
    recipient_type = models.CharField(max_length=3, choices=RECIPIENT_CHOICES, null=False)
    recipient_id = models.CharField(max_length=126, null=True)
    content_type = models.CharField(max_length=3, choices=MessagingEvent.CONTENT_CHOICES, null=False)

    # Only used when content_type is CONTENT_SMS_SURVEY or CONTENT_IVR_SURVEY
    form_unique_id = models.CharField(max_length=126, null=True)
    form_name = models.TextField(null=True)
    xforms_session = models.ForeignKey('smsforms.SQLXFormsSession', null=True, on_delete=models.PROTECT)

    # If this was a reminder that spawned off of a case, this is the case's id
    case_id = models.CharField(max_length=126, null=True)
    status = models.CharField(max_length=3, choices=MessagingEvent.STATUS_CHOICES, null=False)
    error_code = models.CharField(max_length=126, null=True)
    additional_error_text = models.TextField(null=True)

    class Meta:
        app_label = 'sms'

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
        if (parent.source != MessagingEvent.SOURCE_KEYWORD and
                (parent.recipient_id != self.recipient_id or self.recipient_id is None) and
                parent.recipient_type not in (
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


class SelfRegistrationInvitation(models.Model):
    PHONE_TYPE_ANDROID = 'android'
    PHONE_TYPE_OTHER = 'other'
    PHONE_TYPE_CHOICES = (
        (PHONE_TYPE_ANDROID, ugettext_lazy('Android')),
        (PHONE_TYPE_OTHER, ugettext_lazy('Other')),
    )

    STATUS_PENDING = 'pending'
    STATUS_REGISTERED = 'registered'
    STATUS_EXPIRED = 'expired'

    domain = models.CharField(max_length=126, null=False, db_index=True)
    phone_number = models.CharField(max_length=30, null=False, db_index=True)
    token = models.CharField(max_length=126, null=False, unique=True, db_index=True)
    app_id = models.CharField(max_length=126, null=True)
    expiration_date = models.DateField(null=False)
    created_date = models.DateTimeField(null=False)
    phone_type = models.CharField(max_length=20, null=True, choices=PHONE_TYPE_CHOICES)
    registered_date = models.DateTimeField(null=True)

    # True if we are assuming that the recipient has an Android phone
    android_only = models.BooleanField(default=False)

    # True to make email address a required field on the self-registration page
    require_email = models.BooleanField(default=False)

    # custom user data that will be set to the CommCareUser's user_data property
    # when it is created
    custom_user_data = jsonfield.JSONField(default=dict)

    class Meta:
        app_label = 'sms'

    @property
    @memoized
    def odk_url(self):
        if not self.app_id:
            return None

        try:
            return self.get_app_odk_url(self.domain, self.app_id)
        except Http404:
            return None

    @property
    def already_registered(self):
        return self.registered_date is not None

    @property
    def expired(self):
        """
        The invitation is valid until 11:59pm UTC on the expiration date.
        """
        return datetime.utcnow().date() > self.expiration_date

    @property
    def status(self):
        if self.already_registered:
            return self.STATUS_REGISTERED
        elif self.expired:
            return self.STATUS_EXPIRED
        else:
            return self.STATUS_PENDING

    def completed(self):
        self.registered_date = datetime.utcnow()
        self.save()

    def send_step1_sms(self, custom_message=None):
        from corehq.apps.sms.api import send_sms

        if self.android_only:
            self.send_step2_android_sms(custom_message)
            return

        send_sms(
            self.domain,
            None,
            self.phone_number,
            custom_message or get_message(MSG_MOBILE_WORKER_INVITATION_START, domain=self.domain)
        )

    def send_step2_java_sms(self):
        from corehq.apps.sms.api import send_sms
        send_sms(
            self.domain,
            None,
            self.phone_number,
            get_message(MSG_MOBILE_WORKER_JAVA_INVITATION, context=(self.domain,), domain=self.domain)
        )

    def get_user_registration_url(self):
        from corehq.apps.users.views.mobile.users import CommCareUserSelfRegistrationView
        return absolute_reverse(
            CommCareUserSelfRegistrationView.urlname,
            args=[self.domain, self.token]
        )

    @classmethod
    def get_app_info_url(cls, domain, app_id):
        from corehq.apps.sms.views import InvitationAppInfoView
        return absolute_reverse(
            InvitationAppInfoView.urlname,
            args=[domain, app_id]
        )

    @classmethod
    def get_sms_install_link(cls, domain, app_id):
        """
        If CommCare detects this SMS on the phone during start up,
        it gives the user the option to install the given app.
        """
        app_info_url = cls.get_app_info_url(domain, app_id)
        return '[commcare app - do not delete] %s' % base64.b64encode(app_info_url)

    def send_step2_android_sms(self, custom_message=None):
        from corehq.apps.sms.api import send_sms

        registration_url = self.get_user_registration_url()

        if custom_message:
            message = custom_message.format(registration_url)
        else:
            message = get_message(MSG_MOBILE_WORKER_ANDROID_INVITATION, context=(registration_url,),
                domain=self.domain)

        send_sms(
            self.domain,
            None,
            self.phone_number,
            message
        )

        if self.odk_url:
            send_sms(
                self.domain,
                None,
                self.phone_number,
                self.get_sms_install_link(self.domain, self.app_id),
            )

    def expire(self):
        self.expiration_date = datetime.utcnow().date() - timedelta(days=1)
        self.save()

    @classmethod
    def get_unexpired_invitations(cls, phone_number):
        current_date = datetime.utcnow().date()
        return cls.objects.filter(
            phone_number=phone_number,
            expiration_date__gte=current_date,
            registered_date__isnull=True
        )

    @classmethod
    def expire_invitations(cls, phone_number):
        """
        Expire all invitations for the given phone number that have not
        yet expired.
        """
        for invitation in cls.get_unexpired_invitations(phone_number):
            invitation.expire()

    @classmethod
    def by_token(cls, token):
        try:
            return cls.objects.get(token=token)
        except cls.DoesNotExist:
            return None

    @classmethod
    def by_phone(cls, phone_number, expire_duplicates=True):
        """
        Look up the unexpired invitation for the given phone number.
        In the case of duplicates, only the most recent invitation
        is returned.
        If expire_duplicates is True, then any duplicates are automatically
        expired.
        Returns the invitation, or None if no unexpired invitations exist.
        """
        phone_number = apply_leniency(phone_number)
        result = cls.get_unexpired_invitations(phone_number).order_by('-created_date')

        if len(result) == 0:
            return None

        invitation = result[0]
        if expire_duplicates and len(result) > 1:
            for i in result[1:]:
                i.expire()

        return invitation

    @classmethod
    def get_app_odk_url(cls, domain, app_id):
        """
        Get the latest starred build (or latest build if none are
        starred) for the app and return it's odk install url.
        """
        app = get_app(domain, app_id, latest=True)

        if not app.copy_of:
            # If latest starred build is not found, use the latest build
            app = get_app(domain, app_id, latest=True, target='build')

        if not app.copy_of:
            # If no build is found, return None
            return None

        return app.get_short_odk_url(with_media=True)

    @classmethod
    def initiate_workflow(cls, domain, users, app_id=None,
            days_until_expiration=30, custom_first_message=None,
            android_only=False, require_email=False):
        """
        If app_id is passed in, then an additional SMS will be sent to Android
        phones containing a link to the latest starred build (or latest
        build if no starred build exists) for the app. Once ODK is installed,
        it will automatically search for this SMS and install this app.

        If app_id is left blank, the additional SMS is not sent, and once
        ODK is installed it just skips the automatic app install step.
        """
        success_numbers = []
        invalid_format_numbers = []
        numbers_in_use = []

        for user_info in users:
            phone_number = apply_leniency(user_info.phone_number)
            try:
                CommCareMobileContactMixin.validate_number_format(phone_number)
            except InvalidFormatException:
                invalid_format_numbers.append(phone_number)
                continue

            if PhoneNumber.by_phone(phone_number, include_pending=True):
                numbers_in_use.append(phone_number)
                continue

            cls.expire_invitations(phone_number)

            expiration_date = (datetime.utcnow().date() +
                timedelta(days=days_until_expiration))

            invitation = cls(
                domain=domain,
                phone_number=phone_number,
                token=uuid.uuid4().hex,
                app_id=app_id,
                expiration_date=expiration_date,
                created_date=datetime.utcnow(),
                android_only=android_only,
                require_email=require_email,
                custom_user_data=user_info.custom_user_data or {},
            )

            if android_only:
                invitation.phone_type = cls.PHONE_TYPE_ANDROID

            invitation.save()
            invitation.send_step1_sms(custom_first_message)
            success_numbers.append(phone_number)

        return (success_numbers, invalid_format_numbers, numbers_in_use)

    @classmethod
    def send_install_link(cls, domain, users, app_id, custom_message=None):
        """
        This method sends two SMS to each user: 1) an SMS with the link to the
        Google Play store to install Commcare, and 2) an install SMS for the
        given app.

        Use this method to reinstall CommCare on a user's phone. The user must
        already have a mobile worker account. If the user doesn't yet have a
        mobile worker account, use SelfRegistrationInvitation.initiate_workflow()
        so that they can set one up as part of the process.

        :param domain: the name of the domain this request is for
        :param users: a list of SelfRegistrationUserInfo objects
        :param app_id: the app_id of the app for which to send the install link
        :param custom_message: (optional) a custom message to use when sending the
        Google Play URL.
        """
        from corehq.apps.sms.api import send_sms, send_sms_to_verified_number

        if custom_message:
            custom_message = custom_message.format(GOOGLE_PLAY_STORE_COMMCARE_URL)

        domain_translated_message = custom_message or get_message(
            MSG_REGISTRATION_INSTALL_COMMCARE,
            domain=domain,
            context=(GOOGLE_PLAY_STORE_COMMCARE_URL,)
        )
        sms_install_link = cls.get_sms_install_link(domain, app_id)

        success_numbers = []
        invalid_format_numbers = []
        error_numbers = []

        for user in users:
            try:
                CommCareMobileContactMixin.validate_number_format(user.phone_number)
            except InvalidFormatException:
                invalid_format_numbers.append(user.phone_number)
                continue

            phone_number = PhoneNumber.by_phone(user.phone_number)
            if phone_number:
                if phone_number.domain != domain:
                    error_numbers.append(user.phone_number)
                    continue
                user_translated_message = custom_message or get_message(
                    MSG_REGISTRATION_INSTALL_COMMCARE,
                    verified_number=phone_number,
                    context=(GOOGLE_PLAY_STORE_COMMCARE_URL,)
                )
                send_sms_to_verified_number(phone_number, user_translated_message)
                send_sms_to_verified_number(phone_number, sms_install_link)
            else:
                send_sms(domain, None, user.phone_number, domain_translated_message)
                send_sms(domain, None, user.phone_number, sms_install_link)

            success_numbers.append(user.phone_number)

        return (success_numbers, invalid_format_numbers, error_numbers)


class ActiveMobileBackendManager(models.Manager):

    def get_queryset(self):
        return super(ActiveMobileBackendManager, self).get_queryset().filter(deleted=False)


class SQLMobileBackend(UUIDGeneratorMixin, models.Model):
    SMS = 'SMS'
    IVR = 'IVR'

    TYPE_CHOICES = (
        (SMS, ugettext_lazy('SMS')),
        (IVR, ugettext_lazy('IVR')),
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

    class Meta:
        db_table = 'messaging_mobilebackend'
        app_label = 'sms'

    @quickcache(['self.pk', 'domain'], timeout=5 * 60)
    def domain_is_shared(self, domain):
        """
        Returns True if this backend has been shared with domain and domain
        has accepted the invitation.
        """
        count = self.mobilebackendinvitation_set.filter(domain=domain, accepted=True).count()
        return count > 0

    def domain_is_authorized(self, domain):
        """
        Returns True if the given domain is authorized to use this backend.
        """
        return (self.is_global or
                domain == self.domain or
                self.domain_is_shared(domain))

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
        backend_classes = smsutil.get_backend_classes()
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
        for k, v in kwargs.iteritems():
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
        return super(SQLMobileBackend, self).delete(*args, **kwargs)


class SQLSMSBackend(SQLMobileBackend):

    class Meta:
        proxy = True
        app_label = 'sms'

    def get_sms_rate_limit(self):
        """
        Override to use rate limiting. Return None to not use rate limiting,
        otherwise return the maximum number of SMS that should be sent by
        this backend instance in a one minute period.
        """
        return None

    def send(self, msg, *args, **kwargs):
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def get_opt_in_keywords(cls):
        """
        Override to specify a set of opt-in keywords to use for this
        backend type.
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

    def get_load_balance_redis_key(self):
        return 'load-balance-phones-for-backend-%s' % self.pk

    def get_next_phone_number(self):
        if (
            not isinstance(self.load_balancing_numbers, list) or
            len(self.load_balancing_numbers) == 0
        ):
            raise Exception("Expected load_balancing_numbers to not be "
                            "empty for backend %s" % self.pk)

        if len(self.load_balancing_numbers) == 1:
            # If there's just one number, no need to go through the
            # process to figure out which one is next.
            return self.load_balancing_numbers[0]

        redis_key = self.get_load_balance_redis_key()
        return load_balance(redis_key, self.load_balancing_numbers)


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
        self.backend_map_tuples = backend_map.items()
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
    """
    class Meta:
        db_table = 'messaging_mobilebackendmapping'
        app_label = 'sms'
        unique_together = ('domain', 'backend_type', 'prefix')

    couch_id = models.CharField(max_length=126, null=True, db_index=True)

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

    class Meta:
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

    class Meta:
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

    class Meta:
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
    override_open_sessions = models.NullBooleanField()

    # List of doc types representing the only types of contacts who should be
    # able to invoke this keyword. Empty list means anyone can invoke.
    # Example: ['CommCareUser', 'CommCareCase']
    initiator_doc_type_filter = jsonfield.JSONField(default=list)

    last_modified = models.DateTimeField(auto_now=True)

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
    form_unique_id = models.CharField(max_length=126, null=True)

    # Only used for action == ACTION_STRUCTURED_SMS
    # Set to True if the expected structured SMS format should name the values
    # being passed. For example the format "register name=joe age=20" would set
    # this to True, while the format "register joe 20" would set it to False.
    use_named_args = models.NullBooleanField()

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

        if self.action in [self.ACTION_SMS_SURVEY, self.ACTION_STRUCTURED_SMS] and not self.form_unique_id:
            raise self.InvalidModelStateException("Expected a value for form_unique_id")

        super(KeywordAction, self).save(*args, **kwargs)


from corehq.apps.sms import signals

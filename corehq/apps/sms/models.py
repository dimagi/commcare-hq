#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import json_field
import logging
import uuid
import uuidfield
from dimagi.ext.couchdbkit import *

from datetime import datetime, timedelta
from django.db import models, transaction
from collections import namedtuple
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Form
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.migration import (SyncCouchToSQLMixin,
    SyncSQLToCouchMixin)
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.mixin import (CommCareMobileContactMixin,
    PhoneNumberInUseException, InvalidFormatException, VerifiedNumber,
    apply_leniency, BadSMSConfigException)
from corehq.apps.sms import util as smsutil
from corehq.apps.sms.messages import (MSG_MOBILE_WORKER_INVITATION_START,
    MSG_MOBILE_WORKER_ANDROID_INVITATION, MSG_MOBILE_WORKER_JAVA_INVITATION,
    get_message)
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.couch import CouchDocLockableMixIn
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


class MessageLog(SafeSaveDocument, UnicodeMixIn):
    base_doc                    = "MessageLog"
    couch_recipient_doc_type    = StringProperty() # "CommCareCase", "CommCareUser", "WebUser"
    couch_recipient             = StringProperty() # _id of the contact who this sms was sent to/from
    phone_number                = StringProperty()
    direction                   = StringProperty()
    date                        = DateTimeProperty()
    domain                      = StringProperty()
    backend_api                 = StringProperty() # This must be set to <backend module>.API_ID in order to process billing correctly
    backend_id                  = StringProperty()
    billed                      = BooleanProperty(default=False)
    billing_errors              = ListProperty()
    chat_user_id = StringProperty() # For outgoing sms only: if this sms was sent from a chat window, the _id of the CouchUser who sent this sms; otherwise None
    workflow = StringProperty() # One of the WORKFLOW_* constants above describing what kind of workflow this sms was a part of
    # Points to the couch_id of an instance of SQLXFormsSession
    # that this message is tied to
    xforms_session_couch_id = StringProperty()
    reminder_id = StringProperty() # Points to the _id of an instance of corehq.apps.reminders.models.CaseReminder that this sms is tied to
    processed = BooleanProperty(default=True)
    datetime_to_process = DateTimeProperty()
    num_processing_attempts = IntegerProperty(default=0)
    error = BooleanProperty(default=False)
    system_error_message = StringProperty()
    # If the message was simulated from a domain, this is the domain
    domain_scope = StringProperty()
    queued_timestamp = DateTimeProperty()
    processed_timestamp = DateTimeProperty()
    # If this outgoing message is a reply to an inbound message, then this is
    # the _id of the inbound message
    # TODO: For now this is a placeholder and needs to be implemented
    in_reply_to = StringProperty()
    system_phone_number = StringProperty()
    # Set to True to send the message regardless of whether the destination
    # phone number has opted-out. Should only be used to send opt-out
    # replies or other info-related queries while opted-out.
    ignore_opt_out = BooleanProperty(default=False)
    location_id = StringProperty()


    def __unicode__(self):
        to_from = (self.direction == INCOMING) and "from" or "to"
        return "Message %s %s" % (to_from, self.phone_number)

    def set_system_error(self, message=None):
        self.error = True
        self.system_error_message = message
        self.save()

    @property
    def username(self):
        name = self.phone_number
        if self.couch_recipient:
            try:
                if self.couch_recipient_doc_type == "CommCareCase":
                    name = CommCareCase.get(self.couch_recipient).name
                else:
                    # Must be a user
                    name = CouchUser.get_by_user_id(self.couch_recipient).username
            except Exception as e:
                pass
        return name
    
    @property
    def recipient(self):
        if self.couch_recipient_doc_type == "CommCareCase":
            return CommConnectCase.get(self.couch_recipient)
        else:
            return CouchUser.get_by_user_id(self.couch_recipient)
    
    @classmethod
    def by_domain_asc(cls, domain):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=[domain, cls.__name__],
                    endkey=[domain, cls.__name__] + [{}],
                    include_docs=True,
                    descending=False)

    @classmethod
    def by_domain_dsc(cls, domain):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=[domain, cls.__name__] + [{}],
                    endkey=[domain, cls.__name__],
                    include_docs=True,
                    descending=True)

    @classmethod
    def count_by_domain(cls, domain, start_date = None, end_date = {}):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        if not end_date:
            end_date = {}
        reduced = cls.view("sms/by_domain",
                            startkey=[domain, cls.__name__] + [start_date],
                            endkey=[domain, cls.__name__] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_incoming_by_domain(cls, domain, start_date = None, end_date = {}):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        if not end_date:
            end_date = {}
        reduced = cls.view("sms/direction_by_domain",
                            startkey=[domain, cls.__name__, "I"] + [start_date],
                            endkey=[domain, cls.__name__, "I"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_outgoing_by_domain(cls, domain, start_date = None, end_date = {}):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        if not end_date:
            end_date = {}
        reduced = cls.view("sms/direction_by_domain",
                            startkey=[domain, cls.__name__, "O"] + [start_date],
                            endkey=[domain, cls.__name__, "O"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0
    
    @classmethod
    def by_domain_date(cls, domain, start_date = None, end_date = {}):
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Log queries not yet implemented for base class")
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=[domain, cls.__name__] + [start_date],
                    endkey=[domain, cls.__name__] + [end_date],
                    include_docs=True)

    @classmethod
    def inbound_entry_exists(cls, contact_doc_type, contact_id, from_timestamp, to_timestamp=None):
        """
        Checks to see if an inbound sms or call exists for the given caller.

        contact_doc_type - The doc_type of the contact (e.g., "CommCareCase")
        contact_id - The _id of the contact
        after_timestamp - The datetime after which to check for the existence of an entry

        return          True if an sms/call exists in the log, False if not.
        """
        if cls.__name__ == "MessageLog":
            raise NotImplementedError("Not implemented for base class")
        from_timestamp_str = json_format_datetime(from_timestamp)
        to_timestamp_str = json_format_datetime(to_timestamp or datetime.utcnow())
        reduced = cls.view("sms/by_recipient",
            startkey=[contact_doc_type, contact_id, cls.__name__, INCOMING, from_timestamp_str],
            endkey=[contact_doc_type, contact_id, cls.__name__, INCOMING, to_timestamp_str],
            reduce=True).all()
        if reduced:
            return (reduced[0]['value'] > 0)
        else:
            return False


class SMSLog(SyncCouchToSQLMixin, MessageLog):
    text = StringProperty()
    # In cases where decoding must occur, this is the raw text received
    # from the gateway
    raw_text = StringProperty()
    # This is the unique message id that the gateway uses to track this
    # message, if applicable.
    backend_message_id = StringProperty()
    # True if this was an inbound message that was an
    # invalid response to a survey question
    invalid_survey_response = BooleanProperty(default=False)

    messaging_subevent_id = IntegerProperty()

    @property
    def outbound_backend(self):
        """appropriate outbound sms backend"""
        if self.backend_id:
            return SQLMobileBackend.load(self.backend_id, is_couch_id=True)
        else:
            return SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                smsutil.clean_phone_number(self.phone_number),
                domain=self.domain
            )

    def __unicode__(self):

        # crop the text (to avoid exploding the admin)
        if len(self.text) < 60: str = self.text
        else: str = "%s..." % (self.text[0:57])

        to_from = (self.direction == INCOMING) and "from" or "to"
        return "%s (%s %s)" % (str, to_from, self.phone_number)

    @classmethod
    def _migration_get_fields(cls):
        return [field for field in SMS._migration_get_fields() if not field.startswith('fri_')]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SMS

    def _migration_automatically_handle_dups(self):
        return True


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
    messaging_subevent = models.ForeignKey('MessagingSubEvent', null=True, on_delete=models.PROTECT)

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
            return CommConnectCase.get(self.couch_recipient)
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


class SMS(SyncSQLToCouchMixin, Log):
    ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS = 'TOO_MANY_UNSUCCESSFUL_ATTEMPTS'
    ERROR_MESSAGE_IS_STALE = 'MESSAGE_IS_STALE'
    ERROR_INVALID_DIRECTION = 'INVALID_DIRECTION'
    ERROR_PHONE_NUMBER_OPTED_OUT = 'PHONE_NUMBER_OPTED_OUT'
    ERROR_INVALID_DESTINATION_NUMBER = 'INVALID_DESTINATION_NUMBER'
    ERROR_MESSAGE_TOO_LONG = 'MESSAGE_TOO_LONG'

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
    }

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

    # If the message was simulated from a domain, this is the domain
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
        app_label = 'sms'

    @classmethod
    def _migration_get_fields(cls):
        return [
            'backend_api',
            'backend_id',
            'backend_message_id',
            'billed',
            'chat_user_id',
            'couch_recipient',
            'couch_recipient_doc_type',
            'date',
            'datetime_to_process',
            'direction',
            'domain',
            'domain_scope',
            'error',
            'fri_id',
            'fri_message_bank_lookup_completed',
            'fri_message_bank_message_id',
            'fri_risk_profile',
            'ignore_opt_out',
            'invalid_survey_response',
            'location_id',
            'messaging_subevent_id',
            'num_processing_attempts',
            'phone_number',
            'processed',
            'processed_timestamp',
            'queued_timestamp',
            'raw_text',
            'reminder_id',
            'system_error_message',
            'system_phone_number',
            'text',
            'workflow',
            'xforms_session_couch_id',
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return SMSLog


class LastReadMessage(SyncCouchToSQLMixin, Document, CouchDocLockableMixIn):
    domain = StringProperty()
    # _id of CouchUser who read it
    read_by = StringProperty()
    # _id of the CouchUser or CommCareCase who the message was sent to
    # or from
    contact_id = StringProperty()
    # _id of the SMSLog entry
    message_id = StringProperty()
    # date of the SMSLog entry, stored here redundantly to prevent a lookup
    message_timestamp = DateTimeProperty()

    @classmethod
    def get_obj(cls, domain, read_by, contact_id, *args, **kwargs):
        return LastReadMessage.view(
            "sms/last_read_message",
            key=["by_user", domain, read_by, contact_id],
            include_docs=True
        ).one()

    @classmethod
    def create_obj(cls, domain, read_by, contact_id, *args, **kwargs):
        obj = LastReadMessage(
            domain=domain,
            read_by=read_by,
            contact_id=contact_id
        )
        obj.save()
        return obj

    @classmethod
    def by_user(cls, domain, user_id, contact_id):
        return cls.get_obj(domain, user_id, contact_id)

    @classmethod
    def by_anyone(cls, domain, contact_id):
        return LastReadMessage.view(
            "sms/last_read_message",
            startkey=["by_anyone", domain, contact_id, {}],
            endkey=["by_anyone", domain, contact_id],
            descending=True,
            include_docs=True
        ).first()

    @classmethod
    def _migration_get_fields(cls):
        return SQLLastReadMessage._migration_get_fields()

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLLastReadMessage


class SQLLastReadMessage(SyncSQLToCouchMixin, models.Model):
    class Meta:
        db_table = 'sms_lastreadmessage'
        app_label = 'sms'
        index_together = [
            ['domain', 'read_by', 'contact_id'],
            ['domain', 'contact_id'],
        ]

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

    @classmethod
    def _migration_get_fields(cls):
        return [
            'domain',
            'read_by',
            'contact_id',
            'message_id',
            'message_timestamp',
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return LastReadMessage


class CallLog(SyncCouchToSQLMixin, MessageLog):
    form_unique_id = StringProperty()
    answered = BooleanProperty(default=False)
    duration = IntegerProperty() # Length of the call in seconds
    gateway_session_id = StringProperty() # This is the session id returned from the backend
    xforms_session_id = StringProperty()
    error_message = StringProperty() # Error message from the gateway, if any
    submit_partial_form = BooleanProperty(default=False) # True to submit a partial form on hangup if it's not completed yet
    include_case_side_effects = BooleanProperty(default=False)
    max_question_retries = IntegerProperty() # Max number of times to retry a question with an invalid response before hanging up
    current_question_retry_count = IntegerProperty(default=0) # A counter of the number of invalid responses for the current question
    use_precached_first_response = BooleanProperty(default=False)
    first_response = StringProperty()
    # The id of the case to submit the form against
    case_id = StringProperty()
    case_for_case_submission = BooleanProperty(default=False)
    messaging_subevent_id = IntegerProperty()

    def __unicode__(self):
        to_from = (self.direction == INCOMING) and "from" or "to"
        return "Call %s %s" % (to_from, self.phone_number)

    @classmethod
    def answered_call_exists(cls, caller_doc_type, caller_id, after_timestamp,
        end_timestamp=None):
        """
        Checks to see if an outbound call exists for the given caller that was successfully answered.
        
        caller_doc_type The doc_type of the caller (e.g., "CommCareCase").
        caller_id       The _id of the caller's document.
        after_timestamp The datetime after which to check for the existence of a call.
        
        return          True if a call exists in the CallLog, False if not.
        """
        start_timestamp = json_format_datetime(after_timestamp)
        end_timestamp = json_format_datetime(end_timestamp or datetime.utcnow())
        calls = cls.view("sms/by_recipient",
                    startkey=[caller_doc_type, caller_id, "CallLog", OUTGOING, start_timestamp],
                    endkey=[caller_doc_type, caller_id, "CallLog", OUTGOING, end_timestamp],
                    reduce=False,
                    include_docs=True).all()
        result = False
        for call in calls:
            if call.answered:
                result = True
                break
        return result

    @classmethod
    def get_call_by_gateway_session_id(cls, gateway_session_id):
        """
        Returns the CallLog object, or None if not found.
        """
        return CallLog.view('sms/call_by_session',
            startkey=[gateway_session_id, {}],
            endkey=[gateway_session_id],
            descending=True,
            include_docs=True,
            limit=1).one()

    @classmethod
    def _migration_get_fields(cls):
        from corehq.apps.ivr.models import Call
        return Call._migration_get_fields()

    @classmethod
    def _migration_get_sql_model_class(cls):
        from corehq.apps.ivr.models import Call
        return Call


class EventLog(SafeSaveDocument):
    base_doc                    = "EventLog"
    domain                      = StringProperty()
    date                        = DateTimeProperty()
    couch_recipient_doc_type    = StringProperty()
    couch_recipient             = StringProperty()


class ExpectedCallbackEventLog(SyncCouchToSQLMixin, EventLog):
    status = StringProperty(choices=[CALLBACK_PENDING,CALLBACK_RECEIVED,CALLBACK_MISSED])
    
    @classmethod
    def by_domain(cls, domain, start_date=None, end_date={}):
        """
        Note that start_date and end_date are expected in JSON format.
        """
        return cls.view("sms/expected_callback_event",
                        startkey=[domain, start_date],
                        endkey=[domain, end_date],
                        include_docs=True).all()

    @classmethod
    def _migration_get_fields(cls):
        return ExpectedCallback._migration_get_fields()

    @classmethod
    def _migration_get_sql_model_class(cls):
        return ExpectedCallback


class ExpectedCallback(SyncSQLToCouchMixin, models.Model):
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

    @classmethod
    def _migration_get_fields(cls):
        return [
            'domain',
            'date',
            'couch_recipient_doc_type',
            'couch_recipient',
            'status',
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return ExpectedCallbackEventLog


class ForwardingRule(Document):
    domain = StringProperty()
    forward_type = StringProperty(choices=FORWARDING_CHOICES)
    keyword = StringProperty()
    backend_id = StringProperty() # id of MobileBackend which will be used to do the forwarding
    
    def retire(self):
        self.doc_type += "-Deleted"
        self.save()


class CommConnectCase(CommCareCase, CommCareMobileContactMixin):

    def get_phone_info(self):
        PhoneInfo = namedtuple(
            'PhoneInfo',
            [
                'requires_entry',
                'phone_number',
                'sms_backend_id',
                'ivr_backend_id',
            ]
        )
        contact_phone_number = self.get_case_property('contact_phone_number')
        contact_phone_number = apply_leniency(contact_phone_number)
        contact_phone_number_is_verified = self.get_case_property('contact_phone_number_is_verified')
        contact_backend_id = self.get_case_property('contact_backend_id')
        contact_ivr_backend_id = self.get_case_property('contact_ivr_backend_id')

        requires_entry = (
            contact_phone_number and
            contact_phone_number != '0' and
            not self.closed and
            not self.doc_type.endswith(DELETED_SUFFIX) and
            # For legacy reasons, any truthy value here suffices
            contact_phone_number_is_verified
        )
        return PhoneInfo(
            requires_entry,
            contact_phone_number,
            contact_backend_id,
            contact_ivr_backend_id
        )

    def get_time_zone(self):
        return self.get_case_property("time_zone")

    def get_language_code(self):
        return self.get_case_property("language_code")

    def get_email(self):
        return self.get_case_property('commcare_email_address')

    @property
    def raw_username(self):
        return self.get_case_property("name")

    @classmethod
    def wrap_as_commconnect_case(cls, case):
        """
        Takes a CommCareCase and wraps it as a CommConnectCase.
        """
        return CommConnectCase.wrap(case.to_json())

    class Meta:
        # This is necessary otherwise couchdbkit will confuse the sms app with casexml
        app_label = "sms"


class PhoneNumber(models.Model):
    """
    Represents a single phone number. This is not intended to be a
    comprehensive list of phone numbers in the system (yet). For
    now, it's only used to prevent sending SMS/IVR to phone numbers who
    have opted out.
    """
    phone_number = models.CharField(max_length=30, unique=True, null=False, db_index=True)

    # True if it's ok to send SMS to this phone number, False if not
    send_sms = models.BooleanField(null=False, default=True)

    # True if it's ok to call this phone number, False if not
    # This is not yet implemented but will be in the future.
    send_ivr = models.BooleanField(null=False, default=True)

    # True to allow this phone number to opt back in, False if not
    can_opt_in = models.BooleanField(null=False, default=True)

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
    def opt_in_sms(cls, phone_number):
        """
        Opts a phone number in to receive SMS.
        Returns True if the number was actually opted-in, False if not.
        """
        try:
            phone_obj = cls.get_by_phone_number(phone_number)
            if phone_obj.can_opt_in:
                phone_obj.send_sms = True
                phone_obj.save()
                return True
        except cls.DoesNotExist:
            pass
        return False

    @classmethod
    def opt_out_sms(cls, phone_number):
        """
        Opts a phone number out from receiving SMS.
        Returns True if the number was actually opted-out, False if not.
        """
        phone_obj = cls.get_or_create(phone_number)[0]
        if phone_obj:
            phone_obj.send_sms = False
            phone_obj.save()
            return True
        return False


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
            case_id=case.get_id if case else None,
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
        from corehq.apps.reminders.models import (METHOD_SMS, METHOD_SMS_SURVEY,
            METHOD_STRUCTURED_SMS, RECIPIENT_SENDER)

        content_type = cls.CONTENT_NONE
        form_unique_id = None
        form_name = None

        for action in keyword.actions:
            if action.recipient == RECIPIENT_SENDER:
                if action.action in (METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS):
                    content_type = cls.CONTENT_SMS_SURVEY
                    form_unique_id = action.form_unique_id
                    form_name = cls.get_form_name_or_none(action.form_unique_id)
                elif action.action == METHOD_SMS:
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
            source_id=keyword.get_id,
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

    parent = models.ForeignKey('MessagingEvent')
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
    odk_url = models.CharField(max_length=126, null=True)
    phone_type = models.CharField(max_length=20, null=True, choices=PHONE_TYPE_CHOICES)
    registered_date = models.DateTimeField(null=True)

    class Meta:
        app_label = 'sms'

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

    def send_step1_sms(self):
        from corehq.apps.sms.api import send_sms
        send_sms(
            self.domain,
            None,
            self.phone_number,
            get_message(MSG_MOBILE_WORKER_INVITATION_START, domain=self.domain)
        )

    def send_step2_java_sms(self):
        from corehq.apps.sms.api import send_sms
        send_sms(
            self.domain,
            None,
            self.phone_number,
            get_message(MSG_MOBILE_WORKER_JAVA_INVITATION, context=(self.domain,), domain=self.domain)
        )

    def send_step2_android_sms(self):
        from corehq.apps.sms.api import send_sms
        from corehq.apps.sms.views import InvitationAppInfoView
        from corehq.apps.users.views.mobile.users import CommCareUserSelfRegistrationView

        registration_url = absolute_reverse(CommCareUserSelfRegistrationView.urlname,
            args=[self.domain, self.token])
        send_sms(
            self.domain,
            None,
            self.phone_number,
            get_message(MSG_MOBILE_WORKER_ANDROID_INVITATION, context=(registration_url,), domain=self.domain)
        )

        """
        # Until odk 2.24 gets released to the Google Play store, this part won't work
        if self.odk_url:
            app_info_url = absolute_reverse(InvitationAppInfoView.urlname,
                args=[self.domain, self.token])
            message = '[commcare app - do not delete] %s' % app_info_url
            send_sms(
                self.domain,
                None,
                self.phone_number,
                message,
            )
        """

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
    def initiate_workflow(cls, domain, phone_numbers, app_id=None,
            days_until_expiration=30):
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

        odk_url = None
        if app_id:
            odk_url = cls.get_app_odk_url(domain, app_id)

        for phone_number in phone_numbers:
            phone_number = apply_leniency(phone_number)
            try:
                CommCareMobileContactMixin.validate_number_format(phone_number)
            except InvalidFormatException:
                invalid_format_numbers.append(phone_number)
                continue

            if VerifiedNumber.by_phone(phone_number, include_pending=True):
                numbers_in_use.append(phone_number)
                continue

            cls.expire_invitations(phone_number)

            expiration_date = (datetime.utcnow().date() +
                timedelta(days=days_until_expiration))

            invitation = cls.objects.create(
                domain=domain,
                phone_number=phone_number,
                token=uuid.uuid4().hex,
                app_id=app_id,
                expiration_date=expiration_date,
                created_date=datetime.utcnow(),
                odk_url=odk_url,
            )

            invitation.send_step1_sms()
            success_numbers.append(phone_number)

        return (success_numbers, invalid_format_numbers, numbers_in_use)


class ActiveMobileBackendManager(models.Manager):
    def get_queryset(self):
        return super(ActiveMobileBackendManager, self).get_queryset().filter(deleted=False)


class SQLMobileBackend(models.Model):
    SMS = 'SMS'
    IVR = 'IVR'

    TYPE_CHOICES = (
        (SMS, ugettext_lazy('SMS')),
        (IVR, ugettext_lazy('IVR')),
    )

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
    supported_countries = json_field.JSONField(default=[])

    # To avoid having many tables with so few records in them, all
    # SMS backends are stored in this same table. This field is a
    # JSON dict which stores any additional fields that the SMS
    # backend subclasses need.
    # NOTE: Do not access this field directly, instead use get_extra_fields()
    # and set_extra_fields()
    extra_fields = json_field.JSONField(default={})

    # For a historical view of sms data, we can't delete backends.
    # Instead, set a deleted flag when a backend should no longer be used.
    deleted = models.BooleanField(default=False)

    # If the backend uses load balancing, this is a JSON list of the
    # phone numbers to load balance over.
    load_balancing_numbers = json_field.JSONField(default=[])

    # The phone number which you can text to or call in order to reply
    # to this backend
    reply_to_phone_number = models.CharField(max_length=126, null=True)

    class Meta:
        db_table = 'messaging_mobilebackend'
        app_label = 'sms'

    def __init__(self, *args, **kwargs):
        super(SQLMobileBackend, self).__init__(*args, **kwargs)
        if not self.couch_id:
            self.couch_id = uuid.uuid4().hex

        if not self.inbound_api_key:
            self.inbound_api_key = uuid.uuid4().hex

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
        couch_id - if True, then backend_id should be the couch_id to use
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
            self.mobilebackendinvitation_set = [
                MobileBackendInvitation(
                    domain=domain,
                    accepted=True,
                ) for domain in domains
            ]

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
    backend = models.ForeignKey('SQLMobileBackend')

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
    backend = models.ForeignKey('SQLMobileBackend')
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


from corehq.apps.sms import signals

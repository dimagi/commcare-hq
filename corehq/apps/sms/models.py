#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import base64
import logging
import uuid
from dimagi.ext.couchdbkit import *

from datetime import datetime, timedelta
from django.db import models
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Form
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.migration import (SyncCouchToSQLMixin,
    SyncSQLToCouchMixin)
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.signals import case_post_save
from corehq.apps.sms.mixin import (CommCareMobileContactMixin, MobileBackend,
    PhoneNumberInUseException, InvalidFormatException, VerifiedNumber,
    apply_leniency)
from corehq.apps.sms import util as smsutil
from corehq.apps.sms.messages import MSG_MOBILE_WORKER_INVITATION, get_message
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.couch import CouchDocLockableMixIn
from django.utils.translation import ugettext_noop

INCOMING = "I"
OUTGOING = "O"

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
            return MobileBackend.load(self.backend_id)
        else:
            return MobileBackend.auto_load(
                smsutil.clean_phone_number(self.phone_number),
                self.domain
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


class SMS(SyncSQLToCouchMixin, models.Model):
    ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS = 'TOO_MANY_UNSUCCESSFUL_ATTEMPTS'
    ERROR_MESSAGE_IS_STALE = 'MESSAGE_IS_STALE'
    ERROR_INVALID_DIRECTION = 'INVALID_DIRECTION'
    ERROR_PHONE_NUMBER_OPTED_OUT = 'PHONE_NUMBER_OPTED_OUT'

    ERROR_MESSAGES = {
        ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS:
            ugettext_noop('Gateway error.'),
        ERROR_MESSAGE_IS_STALE:
            ugettext_noop('Message is stale and will not be processed.'),
        ERROR_INVALID_DIRECTION:
            ugettext_noop('Unknown message direction.'),
        ERROR_PHONE_NUMBER_OPTED_OUT:
            ugettext_noop('Phone number has opted out of receiving SMS.'),
    }

    couch_id = models.CharField(max_length=126, null=True, db_index=True)
    domain = models.CharField(max_length=126, null=True, db_index=True)
    date = models.DateTimeField(null=True, db_index=True)
    couch_recipient_doc_type = models.CharField(max_length=126, null=True, db_index=True)
    couch_recipient = models.CharField(max_length=126, null=True, db_index=True)
    phone_number = models.CharField(max_length=126, null=True, db_index=True)
    direction = models.CharField(max_length=1, null=True)
    text = models.TextField(null=True)

    # In cases where decoding must occur, this is the raw text received
    # from the gateway
    raw_text = models.TextField(null=True)

    """Properties related to processing and billing"""
    datetime_to_process = models.DateTimeField(null=True, db_index=True)
    processed = models.NullBooleanField(default=True, db_index=True)
    num_processing_attempts = models.IntegerField(default=0, null=True)
    queued_timestamp = models.DateTimeField(null=True)
    processed_timestamp = models.DateTimeField(null=True)
    error = models.NullBooleanField(default=False)
    system_error_message = models.TextField(null=True)
    billed = models.NullBooleanField(default=False)

    # If the message was simulated from a domain, this is the domain
    domain_scope = models.CharField(max_length=126, null=True)

    # Set to True to send the message regardless of whether the destination
    # phone number has opted-out. Should only be used to send opt-out
    # replies or other info-related queries while opted-out.
    ignore_opt_out = models.NullBooleanField(default=False)

    """Metadata properties"""
    backend_api = models.CharField(max_length=126, null=True)
    backend_id = models.CharField(max_length=126, null=True)
    system_phone_number = models.CharField(max_length=126, null=True)

    # This is the unique message id that the gateway uses to track this
    # message, if applicable.
    backend_message_id = models.CharField(max_length=126, null=True)

    # Describes what kind of workflow this sms was a part of
    workflow = models.CharField(max_length=126, null=True)

    # For outgoing sms only: if this sms was sent from a chat window,
    # the _id of the CouchUser who sent this sms; otherwise None
    chat_user_id = models.CharField(max_length=126, null=True)

    # If this sms is related to a survey, this points to the couch_id
    # of an instance of SQLXFormsSession that this sms is tied to
    xforms_session_couch_id = models.CharField(max_length=126, null=True, db_index=True)

    # True if this was an inbound message that was an
    # invalid response to a survey question
    invalid_survey_response = models.NullBooleanField(default=False)

    # If this sms is related to a reminder, this points to the _id of a
    # CaseReminder instance that it is tied to
    reminder_id = models.CharField(max_length=126, null=True)
    location_id = models.CharField(max_length=126, null=True)

    # The MessagingSubEvent that this SMS is tied to. Only applies to
    # SMS that are not part of a survey (i.e., xforms_session_couch_id is None)
    messaging_subevent = models.ForeignKey('MessagingSubEvent', null=True, on_delete=models.PROTECT)

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


class LastReadMessage(Document, CouchDocLockableMixIn):
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

class CallLog(MessageLog):
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


class EventLog(SafeSaveDocument):
    base_doc                    = "EventLog"
    domain                      = StringProperty()
    date                        = DateTimeProperty()
    couch_recipient_doc_type    = StringProperty()
    couch_recipient             = StringProperty()

CALLBACK_PENDING = "PENDING"
CALLBACK_RECEIVED = "RECEIVED"
CALLBACK_MISSED = "MISSED"

class ExpectedCallbackEventLog(EventLog):
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

FORWARD_ALL = "ALL"
FORWARD_BY_KEYWORD = "KEYWORD"
FORWARDING_CHOICES = [FORWARD_ALL, FORWARD_BY_KEYWORD]

class ForwardingRule(Document):
    domain = StringProperty()
    forward_type = StringProperty(choices=FORWARDING_CHOICES)
    keyword = StringProperty()
    backend_id = StringProperty() # id of MobileBackend which will be used to do the forwarding
    
    def retire(self):
        self.doc_type += "-Deleted"
        self.save()


class CommConnectCase(CommCareCase, CommCareMobileContactMixin):

    def case_changed(self):
        """
        Syncs verified numbers with this case.
        """
        contact_phone_number = self.get_case_property("contact_phone_number")
        contact_phone_number_is_verified = self.get_case_property("contact_phone_number_is_verified")
        contact_backend_id = self.get_case_property("contact_backend_id")
        contact_ivr_backend_id = self.get_case_property("contact_ivr_backend_id")
        if ((contact_phone_number is None) or (contact_phone_number == "") or
            (str(contact_phone_number) == "0") or self.closed or
            self.doc_type.endswith(DELETED_SUFFIX)):
            try:
                self.delete_verified_number()
            except Exception:
                logging.exception("Could not delete verified number for owner %s" % self._id)
        elif contact_phone_number_is_verified:
            try:
                self.save_verified_number(self.domain, contact_phone_number, True, contact_backend_id, ivr_backend_id=contact_ivr_backend_id, only_one_number_allowed=True)
            except (PhoneNumberInUseException, InvalidFormatException):
                try:
                    self.delete_verified_number()
                except:
                    logging.exception("Could not delete verified number for owner %s" % self._id)
            except Exception:
                logging.exception("Could not save verified number for owner %s" % self._id)

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
        app_label = "sms" # This is necessary otherwise syncdb will confuse the sms app with casexml


def case_changed_receiver(sender, case, **kwargs):
    # the primary purpose of this function is to add/remove verified
    # phone numbers from the case. if the case doesn't have any verified
    # numbers associated with it this is basically a no-op
    contact = CommConnectCase.wrap_as_commconnect_case(case)
    contact.case_changed()


case_post_save.connect(case_changed_receiver, CommCareCase)


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
    ERROR_NO_EMAIL_ADDRESS = 'NO_EMAIL_ADDRESS'

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
        ERROR_NO_EMAIL_ADDRESS:
            ugettext_noop('Recipient has no email address.'),
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

    def create_subevent_for_single_sms(self, recipient_doc_type=None, recipient_id=None, case=None):
        obj = MessagingSubEvent.objects.create(
            parent=self,
            date=datetime.utcnow(),
            recipient_type=MessagingEvent.get_recipient_type_from_doc_type(recipient_doc_type),
            recipient_id=recipient_id,
            content_type=MessagingEvent.CONTENT_SMS,
            case_id=case.get_id if case else None,
            status=MessagingEvent.STATUS_IN_PROGRESS,
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

        from corehq.apps.reminders.models import RECIPIENT_LOCATION
        if recipient and reminder_definition.recipient == RECIPIENT_LOCATION:
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
    domain = models.CharField(max_length=126, null=False, db_index=True)
    phone_number = models.CharField(max_length=30, null=False, db_index=True)
    token = models.CharField(max_length=126, null=False, db_index=True)
    app_id = models.CharField(max_length=126, null=True)
    expiration_dt = models.DateField(null=False)

    def send(self, odk_url=None):
        from corehq.apps.hqwebapp.utils import sign
        from corehq.apps.sms.api import send_sms
        from corehq.apps.users.views.mobile.users import CommCareUserSelfRegistrationView

        registration_url = absolute_reverse(CommCareUserSelfRegistrationView.urlname,
            args=[self.domain, self.token])
        send_sms(
            self.domain,
            None,
            self.phone_number,
            get_message(MSG_MOBILE_WORKER_INVITATION, context=(registration_url,))
        )

        if odk_url:
            send_sms(
                self.domain,
                None,
                self.phone_number,
                'ccapp: %s, signature: %s' % (odk_url, base64.b64encode(sign(odk_url)))
            )

    @classmethod
    def get_app_odk_url(cls, domain, app_id):
        """
        Get the latest starred build for the app and return it's
        odk install url.
        """
        app = get_app(domain, app_id, latest=True)
        return app.get_short_odk_url(with_media=True)

    @classmethod
    def initiate_workflow(cls, domain, phone_numbers, app_id=None,
            days_until_expiration=30):
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

            expiration_dt = (datetime.utcnow().date() +
                timedelta(days=days_until_expiration))

            invitation = cls.objects.create(
                domain=domain,
                phone_number=phone_number,
                token=uuid.uuid4().hex,
                app_id=app_id,
                expiration_dt=expiration_dt,
            )

            invitation.send(odk_url=odk_url)
            success_numbers.append(phone_number)

        return (success_numbers, invalid_format_numbers, numbers_in_use)

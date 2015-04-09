#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import logging
from dimagi.ext.couchdbkit import *

from datetime import datetime
from django.db import models
from corehq.apps.users.models import CouchUser, CommCareUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.signals import case_post_save
from .mixin import CommCareMobileContactMixin, MobileBackend, PhoneNumberInUseException, InvalidFormatException
from corehq.apps.sms import util as smsutil
from dimagi.utils.couch.database import SafeSaveDocument
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.couch import CouchDocLockableMixIn

INCOMING = "I"
OUTGOING = "O"

WORKFLOW_CALLBACK = "CALLBACK"
WORKFLOW_REMINDER = "REMINDER"
WORKFLOW_KEYWORD = "KEYWORD"
WORKFLOW_BROADCAST = "BROADCAST"
WORKFLOW_DEFAULT = 'default'

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))


ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS = "TOO_MANY_UNSUCCESSFUL_ATTEMPTS"
ERROR_MESSAGE_IS_STALE = "MESSAGE_IS_STALE"
ERROR_INVALID_DIRECTION = "INVALID_DIRECTION"
ERROR_PHONE_NUMBER_OPTED_OUT = "PHONE_NUMBER_OPTED_OUT"


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

class SMSLog(MessageLog):
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

class MessageLogOld(models.Model):
    couch_recipient    = models.TextField()
    phone_number       = models.TextField()
    direction          = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    date               = models.DateTimeField()
    text               = models.TextField()
    # hm, this data is duplicate w/ couch, but will make the query much more
    # efficient to store here rather than doing a couch query for each couch user
    domain             = models.TextField()

    class Meta(): 
        db_table = "sms_messagelog"
        managed = False
         
    def __unicode__(self):

        # crop the text (to avoid exploding the admin)
        if len(self.text) < 60: str = self.text
        else: str = "%s..." % (self.text[0:57])

        to_from = (self.direction == INCOMING) and "from" or "to"
        return "%s (%s %s)" % (str, to_from, self.phone_number)
    
    @property
    def username(self):
        if self.couch_recipient:
            return CouchUser.get_by_user_id(self.couch_recipient).username
        return self.phone_number


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

#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
from couchdbkit.ext.django.schema import *

from datetime import datetime
from django.db import models
from corehq.apps.users.models import CouchUser, CommCareUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.parsing import json_format_datetime

INCOMING = "I"
OUTGOING = "O"

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))

MISSED_EXPECTED_CALLBACK = "CALLBACK_MISSED"

EVENT_TYPE_CHOICES = [MISSED_EXPECTED_CALLBACK]

class MessageLog(Document, UnicodeMixIn):
    base_doc                    = "MessageLog"
    couch_recipient_doc_type    = StringProperty(default="CouchUser")
    couch_recipient             = StringProperty()
    phone_number                = StringProperty()
    direction                   = StringProperty()
    date                        = DateTimeProperty()
    domain                      = StringProperty()

    def __unicode__(self):
        to_from = (self.direction == INCOMING) and "from" or "to"
        return "Message %s %s" % (to_from, self.phone_number)

    def delete(self):
        super(MessageLog, self).delete() # Call the "real" delete() method.

    @property
    def username(self):
        if self.couch_recipient:
            if self.couch_recipient_doc_type == "CouchUser":
                return CouchUser.get_by_user_id(self.couch_recipient).username
            elif self.couch_recipient_doc_type == "CommCareCase":
                return CommCareCase.get(self.couch_recipient).name
        return self.phone_number

class SMSLog(MessageLog):
    text = StringProperty()
    
    def __unicode__(self):

        # crop the text (to avoid exploding the admin)
        if len(self.text) < 60: str = self.text
        else: str = "%s..." % (self.text[0:57])

        to_from = (self.direction == INCOMING) and "from" or "to"
        return "%s (%s %s)" % (str, to_from, self.phone_number)
    
    @classmethod
    def all(cls, doc_type=None):
        return MessageLog.view("sms/by_domain",
                    startkey=["SMSLog"],
                    endkey=["SMSLog"] + [{}],
                    include_docs=True,
                    reduce=False)

    @classmethod
    def by_domain_asc(cls, domain, doc_type=None):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=["SMSLog", domain],
                    endkey=["SMSLog", domain] + [{}],
                    include_docs=True,
                    descending=False)

    @classmethod
    def by_domain_dsc(cls, domain, doc_type=None):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=["SMSLog", domain] + [{}],
                    endkey=["SMSLog", domain],
                    include_docs=True,
                    descending=True)

    @classmethod
    def count_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/by_domain",
                            startkey=["SMSLog", domain] + [start_date],
                            endkey=["SMSLog", domain] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_incoming_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=["SMSLog", domain, "I"] + [start_date],
                            endkey=["SMSLog", domain, "I"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_outgoing_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=["SMSLog", domain, "O"] + [start_date],
                            endkey=["SMSLog", domain, "O"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0


class CallLog(MessageLog):
    
    def __unicode__(self):
        to_from = (self.direction == INCOMING) and "from" or "to"
        return "Call %s %s" % (to_from, self.phone_number)
    
    @classmethod
    def all(cls, doc_type=None):
        return MessageLog.view("sms/by_domain",
                    startkey=["CallLog"],
                    endkey=["CallLog"] + [{}],
                    include_docs=True,
                    reduce=False)

    @classmethod
    def by_domain_asc(cls, domain, doc_type=None):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=["CallLog", domain],
                    endkey=["CallLog", domain] + [{}],
                    include_docs=True,
                    descending=False)

    @classmethod
    def by_domain_dsc(cls, domain, doc_type=None):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=["CallLog", domain] + [{}],
                    endkey=["CallLog", domain],
                    include_docs=True,
                    descending=True)

    @classmethod
    def count_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/by_domain",
                            startkey=["CallLog", domain] + [start_date],
                            endkey=["CallLog", domain] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_incoming_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=["CallLog", domain, "I"] + [start_date],
                            endkey=["CallLog", domain, "I"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_outgoing_by_domain(cls, domain, start_date = None, end_date = {}, doc_type=None):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=["CallLog", domain, "O"] + [start_date],
                            endkey=["CallLog", domain, "O"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def inbound_call_exists(cls, verified_number, after_timestamp):
        """
        Checks to see if an inbound call exists for the given number after the given timestamp.
        
        verified_number The VerifiedNumber entry for which to check the existence of a call.
        after_timestamp The datetime after which to check for the existence of a call.
        
        return          True if a call exists in the CallLog, False if not.
        """
        if verified_number is None:
            return False
        start_timestamp = json_format_datetime(after_timestamp)
        end_timestamp = json_format_datetime(datetime.utcnow())
        reduced = MessageLog.view("sms/by_phone_number_direction_date",
                    startkey=["CallLog", verified_number.phone_number, INCOMING] + [start_timestamp],
                    endkey=["CallLog", verified_number.phone_number, INCOMING] + [end_timestamp],
                    reduce=True).all()
        if reduced:
            return (reduced[0]['value'] > 0)
        else:
            return False

class EventLog(Document):
    domain                      = StringProperty()
    date                        = DateTimeProperty()
    couch_recipient_doc_type    = StringProperty()
    couch_recipient             = StringProperty()
    event_type                  = StringProperty(choices=EVENT_TYPE_CHOICES)


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

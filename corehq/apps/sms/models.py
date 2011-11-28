#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
from couchdbkit.ext.django.schema import *

from django.db import models
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.mixins import UnicodeMixIn

INCOMING = "I"
OUTGOING = "O"

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))

class MessageLog(Document, UnicodeMixIn):
    couch_recipient    = StringProperty()
    phone_number       = StringProperty()
    direction          = StringProperty()
    date               = DateTimeProperty()
    text               = StringProperty()
    domain             = StringProperty()

    def __unicode__(self):

        # crop the text (to avoid exploding the admin)
        if len(self.text) < 60: str = self.text
        else: str = "%s..." % (self.text[0:57])

        to_from = (self.direction == INCOMING) and "from" or "to"
        return "%s (%s %s)" % (str, to_from, self.phone_number)

    def delete(self):
        super(MessageLog, self).delete() # Call the "real" delete() method.

    @property
    def username(self):
        if self.couch_recipient:
            return CouchUser.get_by_user_id(self.couch_recipient).username
        return self.phone_number

    # Couch view wrappers
    @classmethod
    def all(cls):
        return MessageLog.view("sms/by_domain", include_docs=True, reduce=False)

    @classmethod
    def by_domain_asc(cls, domain):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=[domain],
                    endkey=[domain] + [{}],
                    include_docs=True,
                    descending=False)

    @classmethod
    def by_domain_dsc(cls, domain):
        return cls.view("sms/by_domain",
                    reduce=False,
                    startkey=[domain] + [{}],
                    endkey=[domain],
                    include_docs=True,
                    descending=True)

    @classmethod
    def count_by_domain(cls, domain, start_date = None, end_date = {}):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/by_domain",
                            startkey=[domain] + [start_date],
                            endkey=[domain] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_incoming_by_domain(cls, domain, start_date = None, end_date = {}):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=[domain, "I"] + [start_date],
                            endkey=[domain, "I"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0

    @classmethod
    def count_outgoing_by_domain(cls, domain, start_date = None, end_date = {}):
        if not end_date:
            end_date = {}
        reduced = MessageLog.view("sms/direction_by_domain",
                            startkey=[domain, "O"] + [start_date],
                            endkey=[domain, "O"] + [end_date],
                            reduce=True).all()
        if reduced:
            return reduced[0]['value']
        return 0




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
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

    @property
    def username(self):
        if self.couch_recipient:
            return CouchUser.get_by_user_id(self.couch_recipient).username
        return self.phone_number

    # Couch view wrappers
    @classmethod
    def all(cls):
        return CouchUser.view("sms/by_domain", include_docs=True)

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




class MessageLogOld(models.Model):
    couch_recipient    = models.TextField()
    phone_number       = models.TextField()
    direction          = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    date               = models.DateTimeField()
    text               = models.TextField()
    # hm, this data is duplicate w/ couch, but will make the query much more
    # efficient to store here rather than doing a couch query for each couch user
    domain             = models.TextField()

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
#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from corehq.apps.users.models import CouchUser, CommCareUser

INCOMING = "I"
OUTGOING = "O"

DIRECTION_CHOICES = (
    (INCOMING, "Incoming"),
    (OUTGOING, "Outgoing"))

class MessageLog(models.Model):
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
            try:
                user = CouchUser.get(self.couch_recipient)
                return user.username
            except Exception:
                return CommCareUser.get_by_user_id(self.couch_recipient).username
        return self.phone_number
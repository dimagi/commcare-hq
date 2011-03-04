from django.db import models
from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn
from datetime import datetime, timedelta

class FormRepeater(Document, UnicodeMixIn):
    """
    Record of forms repeating to a new url.
    """
    domain = StringProperty()
    url = StringProperty()
    
    def __unicode__(self):
        return "forwarding to: %s" % self.url

class RepeatRecord(DocumentSchema, UnicodeMixIn):
    """
    Record of something being repeated to something.
    These get injected into XForms.
    """
    url = StringProperty()
    last_checked = DateTimeProperty()
    next_check = DateTimeProperty()
    succeeded = BooleanProperty(default=False)
    
    def update_success(self):
        # we use an exponential backoff to avoid submitting to bad urls
        # too frequently.
        self.last_checked = datetime.utcnow()
        self.next_check = None
        self.succeeded = True
    
    def update_failure(self):
        # we use an exponential backoff to avoid submitting to bad urls
        # too frequently.
        assert(self.succeeded == False)
        window = self.next_check - self.last_checked if self.last_checked else timedelta(minutes=30)
        self.last_checked = datetime.utcnow()
        self.next_check = datetime.utcnow() + window
        
    def try_now(self):
        # try when we haven't succeeded and either we've
        # never checked, or it's time to check again
        return not self.succeeded and self.next_check is None \
                or self.next_check < datetime.utcnow() 

# import signals
from corehq.apps.receiverwrapper import signals
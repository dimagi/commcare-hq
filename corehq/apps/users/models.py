from django.db import models
from django.conf import settings
from djangocouchuser.models import CouchUserProfile

class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """
    
    def __unicode__(self):
        return "%s @ %s" % (self.user)
    
# load our signals.
import corehq.apps.users.signals

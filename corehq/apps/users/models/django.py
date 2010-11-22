"""
Django  models go here
"""
from djangocouchuser.models import CouchUserProfile
from corehq.apps.users.models.couch import CouchUser

class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """

    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "%s @ %s" % (self.user)

    def get_couch_user(self):
        couch_user = CouchUser.get(self._id)
        return couch_user

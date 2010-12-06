"""
Django  models go here
"""
from __future__ import absolute_import
import datetime
from django.contrib.auth.models import User
from django.db import models
from djangocouchuser.models import CouchUserProfile
from corehq.apps.users.models.couch import CouchUser

class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """
    is_commcare_user = models.BooleanField(default=False)

    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "%s @ %s" % (self.user)

    def get_couch_user(self):
        couch_user = CouchUser.get(self._id)
        return couch_user

def create_django_user_from_registration_data(username, password):
    """From registration xml data, automatically build a django user"""
    user = User()
    user.username = username
    user.set_password(password)
    user.first_name = ''
    user.last_name  = ''
    user.email = ""
    user.is_staff = False # Can't log in to admin site
    user.is_active = True # Activated upon receipt of confirmation
    user.is_superuser = False # Certainly not, although this makes login sad
    user.last_login =  datetime.datetime(1970,1,1)
    user.date_joined = datetime.datetime.utcnow()
    user.is_commcare_user = True
    return user

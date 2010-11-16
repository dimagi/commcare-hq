from __future__ import absolute_import
import logging
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable, User
from djangocouchuser.signals import couch_user_post_save
from corehq.apps.users.models import HqUserProfile
from couchforms.signals import xform_saved
from couchforms.models import XFormInstance

# xmlns that registrations and backups come in as, respectively. 
REGISTRATION_XMLNS = "http://openrosa.org/user-registration"

"""
Case 1: 
This section automatically creates Couch users whenever a web user is created
"""
def create_user_from_django_user(sender, instance, created, **kwargs): 
    """
    The user post save signal, to auto-create our Profile
    """
    if not created:
        try:
            instance.get_profile().save()
            return
        except HqUserProfile.DoesNotExist:
            logging.warn("There should have been a profile for "
                         "%s but wasn't.  Creating one now." % instance)
        except SiteProfileNotAvailable:
            raise
    
    profile, created = HqUserProfile.objects.get_or_create(user=instance)

    if not created:
        # magically calls our other save signal
        profile.save()
        
post_save.connect(create_user_from_django_user, User)        
post_save.connect(couch_user_post_save, HqUserProfile)


import logging
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable, User
from djangocouchuser.signals import couch_user_post_save
from corehq.apps.users.models import HqUserProfile

def user_post_save(sender, instance, created, **kwargs): 
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
        
post_save.connect(user_post_save, User)        
post_save.connect(couch_user_post_save, HqUserProfile)

from django.db.models.signals import post_init, post_save, pre_save, pre_delete
from django.contrib.auth.models import User
from django.db.models import Q
import logging
from datetime import datetime
import settings
try:
    from corehq.util.threadlocals import get_current_user
except:
    from auditcare.utils import get_current_user

from django.db import transaction
from models import *


def audit_save(sender, instance, created, **kwargs):
    usr = get_current_user()
    #really stupid sanity check for unit tests when threadlocals doesn't update and user model data is updated.
    if usr != None:
        try:
            User.objects.get(id=usr.id)
        except:
            usr = None
    AuditEvent.objects.audit_save(sender, instance, usr)

if hasattr(settings, 'AUDIT_MODEL_SAVE'):
    for full_str in settings.AUDIT_MODEL_SAVE:
        comps = full_str.split('.')
        model_class = comps[-1]
        mod_str = '.'.join(comps[0:-1])
        mod = __import__(mod_str, {},{},[model_class])        
        if hasattr(mod, model_class):            
            audit_model = getattr(mod, model_class)       
            post_save.connect(audit_save, sender=audit_model, dispatch_uid="audit_save_" + str(model_class)) #note, you should add a unique dispatch_uid to this else you might get dupes
            #source; http://groups.google.com/group/django-users/browse_thread/thread/0f8db267a1fb036f
else:
    logging.warning("You do not have the AUDIT_MODEL_SAVE settings variable setup.  If you want to setup model save audit events, please add the property and populate it with fully qualified model names.")
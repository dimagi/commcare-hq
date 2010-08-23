from django.db.models.signals import post_init, post_save, pre_save
from django.contrib.auth.models import User
from django.db.models import Q
import logging
from datetime import datetime
import settings
from shared_code.threadlocals import get_current_user
from models import AuditEvent


def audit_save(sender, instance, **kwargs):
    #crap, threadlocals is a middleware, where should it be accessed?
    usr = get_current_user()        
    AuditEvent.objects.audit_save(sender, instance, usr)

if hasattr(settings, 'AUDIT_MODEL_SAVE'):
    for full_str in settings.AUDIT_MODEL_SAVE:
        comps = full_str.split('.')
        model_class = comps[-1]
        mod_str = '.'.join(comps[0:-1])
        mod = __import__(mod_str, {},{},[model_class])        
        if hasattr(mod, model_class):            
            audit_model = getattr(mod, model_class)            
            post_save.connect(audit_save, sender=audit_model)
else:
    logging.warning("You do not have the AUDIT_MODEL_SAVE settings variable setup.  If you want to setup model save audit events, please add the property and populate it with fully qualified model names.")
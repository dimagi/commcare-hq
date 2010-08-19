from django.db.models.signals import post_init, post_save
from django.contrib.auth.models import User
from django.db.models import Q
import logging
from datetime import datetime
import settings
from models import AuditEvent


def track_access(sender, instance, **kwargs):
    #crap, threadlocals is a middleware, where should it be accessed?
    #threadlocals.get_current_user()    
    at = AuditEvent(content_object=instance, user=User.objects.all()[0])
    at.save()

if hasattr(settings, 'AUDITABLE_MODELS'):
    for full_str in settings.AUDITABLE_MODELS:
        comps = full_str.split('.')
        model_class = comps[-1]
        mod_str = '.'.join(comps[0:-1])
        mod = __import__(mod_str, {},{},[model_class])        
        if hasattr(mod, model_class):            
            audit_model = getattr(mod, model_class)            
            #post_init.connect(track_access, sender=audit_model)
            post_save.connect(track_access, sender=audit_model)
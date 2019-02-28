from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.db.models.query import QuerySet

from dimagi.ext.couchdbkit import Document
from dimagi.ext.jsonobject import JsonObject
from django.db.models.signals import post_save
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.forms import model_to_dict

try:
    from dimagi.utils.threadlocals import get_current_user
except:
    from auditcare.utils import get_current_user

from django.dispatch import Signal

log = logging.getLogger(__name__)
user_login_failed = Signal(providing_args=['request', 'username'])


def model_to_json(instance):
    """
    converts a django model into json in the format used by jsonobject

    """

    class DummyObject(JsonObject):
        pass

    json_model = model_to_dict(instance)
    for key, value in json_model.items():
        if isinstance(value, QuerySet):
            json_model[key] = list(value)

    return DummyObject(**json_model).to_json()


def django_audit_save(sender, instance, created, raw=False, **kwargs):
    """
    Audit Save is a signal to attach post_save to any arbitrary django model
    """
    if raw:
        return

    usr = get_current_user()

    instance_json = model_to_json(instance)

    #really stupid sanity check for unit tests when threadlocals doesn't update and user model data is updated.
    if usr != None:
        try:
            User.objects.get(id=usr.id)
        except:
            usr = None
    from auditcare.models import AuditEvent
    AuditEvent.audit_django_save(sender, instance, instance_json, usr)


def couch_audit_save(instance, *args, **kwargs):
    instance.__orig_save(*args, **kwargs)
    instance_json = instance.to_json()
    from auditcare.models import AuditEvent
    usr = get_current_user()
    if usr != None:
        try:
            User.objects.get(id=usr.id)
        except:
            usr = None
    AuditEvent.audit_couch_save(instance.__class__, instance, instance_json, usr)


if not hasattr(settings, 'AUDIT_MODEL_SAVE'):
    log.warning("You do not have the AUDIT_MODEL_SAVE settings variable setup.  If you want to setup model save audit events, please add the property and populate it with fully qualified model names.")
    settings.AUDIT_MODEL_SAVE = []

if hasattr(settings, 'AUDIT_DJANGO_USER'):
    do_audit_django_user = settings.AUDIT_DJANGO_USER
else:
    do_audit_django_user = False

if do_audit_django_user:
    settings.AUDIT_MODEL_SAVE.append('django.contrib.auth.models.User')

for full_str in settings.AUDIT_MODEL_SAVE:
    comps = full_str.split('.')
    model_class = comps[-1]
    mod_str = '.'.join(comps[0:-1])
    mod = __import__(mod_str, {}, {}, [str(model_class)])
    if hasattr(mod, model_class):
        audit_model = getattr(mod, model_class)
        if issubclass(audit_model, models.Model):
            # it's a django model subclass.
            post_save.connect(django_audit_save, sender=audit_model, dispatch_uid="audit_save_" + str(model_class)) #note, you should add a unique dispatch_uid to this else you might get dupes
            # source; http://groups.google.com/group/django-users/browse_thread/thread/0f8db267a1fb036f
        elif issubclass(audit_model, Document):
            # it's a couchdbkit Document subclass
            audit_model.__orig_save = audit_model.save
            audit_model.save = couch_audit_save

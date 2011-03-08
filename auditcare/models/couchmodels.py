import copy
from couchdbkit.ext.django.schema import Document
from couchdbkit.schema.properties import StringProperty, DateTimeProperty, StringListProperty, DictProperty
from django.db import models
from django.utils.translation import ugettext_lazy as _
import uuid
from django.contrib.auth.models import User, AnonymousUser

from datetime import datetime, timedelta
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db.models.query import QuerySet
from django.utils.http import urlquote
import logging
import hashlib
import json
from auditcare import utils
from dimagi.utils.couch.database import get_db

try:
    from django.contrib.auth.signals import user_logged_in, user_logged_out
except:
    logging.error("Error, django.contrib.auth signals not available in this version of django yet.")
    user_logged_in = None
    user_logged_out = None

from auditcare.signals import user_login_failed

def make_uuid():
    return uuid.uuid1().hex
def getdate():
    return datetime.utcnow()

#class AuditManager(models.Manager):
#    pass


class AuditEvent(Document):
    user = StringProperty()
    base_type = StringProperty(default="AuditEvent") #for subclassing this needs to stay consistent
    event_date = DateTimeProperty(default = getdate)
    event_class = StringProperty() #Descriptor classifying this particular instance - this will be the child class's class name
    description = StringProperty() #particular instance details of this audit event

    @property
    def summary(self):
        try:
            ct = ContentType.objects.get(model=self.event_class.lower())
            return ct.model_class().objects.get(id=self.id).summary
        except Exception, e:
            return ""

    class Meta:
        app_label = 'auditcare'


    def __unicode__(self):
        return "[%s] %s" % (self.event_class, self.description)


    @classmethod
    def create_audit(cls, model_class, user):
        """
        Returns a premade audit object in memory to be completed by the subclasses.
        """
        audit = cls()
        audit.event_class= cls.__name__
        if isinstance(user, AnonymousUser):
            audit.user = None
            audit.description = "[AnonymousAccess] "
        elif user == None:
            audit.user = None
            audit.description='[NullUser] '
        elif isinstance(user, User):
            audit.user = user.username
            audit.description = user.first_name + " " + user.last_name
        else:
            audit.user = user.username
            audit.description = ''
        return audit




class ModelActionAudit(AuditEvent):
    """
    Audit event to track the modification or editing of an auditable model

    For django models:
        the object_type will be the contenttype
        the object_uuid will be the model instance's PK
        the revision_id will be whatever is decided by the app

    for couch models:
        the object_type will be the doc_type
        the object_uuid will be theh doc's doc_id
        the revision_id will be the _rev as emitted by the 

    """
    object_type = StringProperty()
    object_uuid = StringProperty()
    revision_checksum = StringProperty()
    revision_id = StringProperty()
    archived_data = DictProperty()

    @property
    def summary(self):
        return "%s ID: %s" % (self.object_type, self.object_uuid)

    class Meta:
        app_label = 'auditcare'

    @classmethod
    def calculate_checksum(cls, instance_json, is_django=False):
        if is_django:
            json_string = json.dumps(instance_json)
        else:
            instance_copy = copy.deepcopy(instance_json)
            #if instance_copy.has_key('_rev'):
                #if it's an existing version, then save it
            instance_copy.pop('_rev')
            json_string = json.dumps(instance_copy)
        return hashlib.sha1(json_string).hexdigest()

    @classmethod
    def _save_model_audit(cls, audit, instance_id, instance_json, revision_id, model_class_name, is_django=False):
        prior_revs = get_db().view('auditcare/model_actions', key=['model_types', model_class_name, instance_id]).all()

        audit.description += "Save %s" % (model_class_name)
        audit.object_type = model_class_name
        audit.object_uuid = instance_id
        audit.archived_data = instance_json
        audit.revision_checksum = cls.calculate_checksum(instance_json, is_django=is_django)

        if len(prior_revs) == 0:
            if is_django:
                audit.revision_id = "1"
            else:
                audit.revision_id = revision_id
            audit.save()
        else:
            #this has been archived before.  Get the last one and compare the checksum.
            sorted_revs = sorted(prior_revs, key=lambda x: x['value']['rev'])
            last_rev = sorted_revs[-1]['value']['rev']
            last_checksum = sorted_revs[-1]['value']['checksum']
            if is_django:
                #for django models, increment an integral counter.
                try:
                    audit.revision_id = str(int(last_rev) + 1)
                except:
                    logging.error("Error, last revision for object %s is not an integer, resetting to one")
                    audit.revision_id = "1"
            else:
                #for django set the revision id to the current document's revision id.
                audit.revision_id = revision_id

            if last_checksum == audit.revision_checksum:
                #no actual changes made on this save, do nothing
                logging.debug("No data change, not creating audit event")
            else:
                audit.save()

    @classmethod
    def audit_django_save(cls, model_class, instance, instance_json, user):
        audit = cls.create_audit(cls, user)
        instance_id = unicode(instance.id)
        revision_id = None
        cls._save_model_audit(audit, instance_id, instance_json, revision_id, model_class.__name__, is_django=True)


    @classmethod
    def audit_couch_save(cls, model_class, instance, instance_json, user):
        audit = cls.create_audit(cls, user)
        instance_id = instance._id
        revision_id = instance._rev
        cls._save_model_audit(audit, instance_id, instance_json, revision_id, model_class.__name__, is_django=False)
setattr(AuditEvent, 'audit_django_save', ModelActionAudit.audit_django_save)
setattr(AuditEvent, 'audit_couch_save', ModelActionAudit.audit_couch_save)





class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """
    request_path = StringProperty()
    ip_address = StringProperty()

    view = StringProperty() #the fully qualifid view name
    headers = DictProperty() #the request.META?
    session_key = StringProperty()

    @property
    def summary(self):
        return "%s from %s" % (self.request_path, self.ip_address)

    class Meta:
        app_label = 'auditcare'


    @classmethod
    def audit_view(cls, request, user, view_func):
        '''Creates an instance of a Access log.
        '''
        try:
            audit = cls.create_audit(cls, user)
            audit.description += "View"
            if len(request.GET.keys()) > 0:
                audit.request_path = "%s?%s" % (request.path, '&'.join(["%s=%s" % (x, request.GET[x]) for x in request.GET.keys()]))
            else:
                audit.request_path = request.path
            audit.ip_address = utils.get_ip(request)
            audit.view = "%s.%s" % (view_func.__module__, view_func.func_name)
            #audit.headers = request.META #it's a bit verbose to go to that extreme, TODO: need to have targeted fields in the META, but due to server differences, it's hard to make it universal.
            audit.session_key = request.session.session_key
            audit.save()
        except Exception, ex:
            logging.error("NavigationEventAudit.audit_view error: %s" % (ex))

setattr(AuditEvent, 'audit_view', NavigationEventAudit.audit_view)

class AccessAudit(AuditEvent):
    ACCESS_CHOICES = (
                      ('login', "Login"),
                      ('logout', "Logout"),
                      ('failed', "Failed Login"),
                      ('password', "Password Change"),
                      )
    access_type = StringProperty(choices=ACCESS_CHOICES)
    ip_address = StringProperty()
    session_key = StringProperty()

    class Meta:
        app_label = 'auditcare'

    @property
    def summary(self):
        return "%s from %s" % (self.access_type, self.ip_address)


    @classmethod
    def audit_login(cls, request, user, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, user)
        audit.ip_address = utils.get_ip(request)
        audit.access_type = 'login'
        audit.description = "Login Success"
        audit.session_key = request.session.session_key
        audit.save()

    @classmethod
    def audit_login_failed(cls, request, username, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, username)
        audit.ip_address = utils.get_ip(request)
        audit.access_type = 'failed'
        if username != None:
            audit.description = "Login Failure: %s" % (username)
        else:
            audit.description = "Login Failure"
        audit.session_key = request.session.session_key
        audit.save()

    @classmethod
    def audit_logout(cls, request, user):
        '''Log a logout event'''
        audit = cls.create_audit(cls, user)
        audit.ip_address = utils.get_ip(request)

        audit.description = "Logout %s" % (user.username)
        audit.access_type = 'logout'
        audit.session_key = request.session.session_key
        audit.save()

setattr(AuditEvent, 'audit_login', AccessAudit.audit_login)
setattr(AuditEvent, 'audit_login_failed', AccessAudit.audit_login_failed)
setattr(AuditEvent, 'audit_logout', AccessAudit.audit_logout)


def audit_login(sender, **kwargs):
    AuditEvent.audit_login(kwargs["request"], kwargs["user"], True) # success

if user_logged_in:
    user_logged_in.connect(audit_login)

def audit_logout(sender, **kwargs):
    AuditEvent.audit_logout(kwargs["request"], kwargs["user"])

if user_logged_out:
    user_logged_out.connect(audit_logout)

def audit_login_failed(sender, **kwargs):
    AuditEvent.audit_login_failed(kwargs["request"], kwargs["username"])
user_login_failed.connect(audit_login_failed)


class FieldAccess(models.Model):
    object_type = StringProperty() #String of ContentType, verbose_name='Case linking content type', blank=True, null=True)
    field = StringProperty()

    class Meta:
        app_label = 'auditcare'

#    class Meta:
#        unique_together = ('object_type', 'field')

class ModelAuditEvent(models.Model):
    object_type = StringProperty() # String of ContentType/Model, verbose_name='Case linking content type', blank=True, null=True)
    object_uuid = StringProperty() #('object_uuid', max_length=32, db_index=True, blank=True, null=True)

    properties = StringListProperty() #models.ManyToManyField(FieldAccess, blank=True, null=True)
    property_data = DictProperty() #models.TextField() #json of the actual fields accessed

    user = StringProperty() # The User's username accessing this
    accessed = DateTimeProperty(default = getdate)

    class Meta:
        app_label = 'auditcare'


import auditcare.signals

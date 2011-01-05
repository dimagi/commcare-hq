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
from auditcare import utils

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
        #print cls.__name__
        if isinstance(user, AnonymousUser):
            audit.user = None
            audit.description = "[AnonymousAccess] "
        elif user == None:
            audit.user = None
            audit.description='[NullUser] '
        else:
            audit.user = user
            audit.description = ''
        return audit



class ModelActionAudit(AuditEvent):
    """
    Audit event to track the modification or editing of an auditable model
    """
    object_type = StringProperty() # The ContentType of the calling object (ContentType, verbose_name='Case linking content type', blank=True, null=True)
    object_uuid = StringProperty #the object_uuid, max_length=32, db_index=True, blank=True, null=True)
    #content_object = generic.GenericForeignKey('object_type', 'object_uuid')

    @property
    def summary(self):
        return "%s ID: %s" % (self.object_type, self.object_uuid)

    class Meta:
        app_label = 'auditcare'

    @classmethod
    def audit_save(cls, model_class, instance, user):
        audit = cls.create_audit(cls, user)
        audit.description += "Save %s" % (model_class.__name__)
        #audit.content_object = instance
        audit.object_type = model_class.__name__
        audit.object_uuid = model_class.id
        audit.save()
setattr(AuditEvent, 'audit_save', ModelActionAudit.audit_save)

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
            #audit.headers = unicode(request.META) #it's a bit verbose to go to that extreme, TODO: need to have targeted fields in the META, but due to server differences, it's hard to make it universal.
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
    def audit_login(cls, request, user, success, username_attempt=None, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, user)
        audit.ip_address = utils.get_ip(request)
        if success:
            audit.access_type = 'login'
            audit.description = "Login Success"
        else:
            audit.access_type = 'failed'
            if username_attempt != None:
                audit.description = "Login Failure: %s" % (username_attempt)
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
setattr(AuditEvent, 'audit_logout', AccessAudit.audit_logout)



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

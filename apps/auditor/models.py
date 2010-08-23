from django.db import models
from django.utils.translation import ugettext_lazy as _
import uuid
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db.models.query import QuerySet
from django.utils.http import urlquote

import utils

def make_uuid():
    return uuid.uuid1().hex
def getdate():
    return datetime.utcnow()

#class AuditManager(models.Manager):
#    pass


class AuditEvent(models.Model):
    user = models.ForeignKey(User, null=True, blank=True)
    event_date = models.DateTimeField(default = getdate)
    event_class = models.CharField(max_length=32, db_index=True, editable=False) #allow user defined classes
    description = models.CharField(max_length=160)

class ModelActionAudit(AuditEvent):
    """
    Audit event to track the modification or editing of an auditable model
    """    
    object_type = models.ForeignKey(ContentType, verbose_name='Case linking content type', blank=True, null=True)
    object_uuid = models.CharField('object_uuid', max_length=32, db_index=True, blank=True, null=True)
    content_object = generic.GenericForeignKey('object_type', 'object_uuid')    
    
    @classmethod
    def audit_save(cls, model_class, instance, user):
        audit = cls()
        audit.user = user 
        audit.description = "Save %s" % (model_class.__name__)        
        audit.event_class= cls.__name__
        audit.content_object = instance        
        audit.save()                
setattr(AuditEvent.objects, 'audit_save', ModelActionAudit.audit_save)
    
   

class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """ 
    request_path = models.TextField()
    ip_address = models.IPAddressField()
    
    view = models.CharField(max_length=255) #the fully qualifid view name
    headers = models.TextField(null=True, blank=True) #the request.META?
    session = models.ForeignKey(Session)
    
    @classmethod
    def audit_view(cls, request, user, view_func):
        '''Creates an instance of a Access log.
        '''
        audit = NavigationEventAudit()
        audit.user = request.user 
        audit.description = "View"
        audit.event_class= cls.__name__       
        if len(request.GET.keys()) > 0: 
            audit.request_path = "%s?%s" % (request.path, '&'.join(["%s=%s" % (x, request.GET[x]) for x in request.GET.keys()]))
        else:
            audit.request_path = request.path        
        audit.ip_address = utils.get_ip(request)
        audit.view = "%s.%s" % (view_func.__module__, view_func.func_name)        
        #audit.headers = unicode(request.META) #it's a bit verbose to go to that extreme, TODO: need to have targeted fields in the META, but due to server differences, it's hard to make it universal.
        audit.session = Session.objects.get(pk=request.session.session_key)
        audit.save()        
setattr(AuditEvent.objects, 'audit_view', NavigationEventAudit.audit_view)
    
class AccessAudit(AuditEvent):
    ACCESS_CHOICES = (
                      ('login', "Login"),
                      ('logout', "Logout"),
                      ('failed', "Failed Login"),
                      ('password', "Password Change"),
                      )
    access_type = models.CharField(choices=ACCESS_CHOICES, max_length=12)
    ip_address = models.IPAddressField()
    session = models.ForeignKey(Session)    
    
    @classmethod
    def audit_login(cls, request, user, success):
        '''Creates an instance of a Access log.
        '''
        audit = AccessAudit() 
        audit.event_class= cls.__name__
        audit.user = user
        audit.ip_address = utils.get_ip(request)
        if success:
            audit.description = "Login Success"
        else:
            audit.description = "Login Failure"
             
        audit.session = Session.objects.get(pk=request.session.session_key)
        audit.save()
setattr(AuditEvent.objects, 'audit_login', AccessAudit.audit_login)

    
class FieldAccess(models.Model):
    object_type = models.ForeignKey(ContentType, verbose_name='Case linking content type', blank=True, null=True)
    field = models.CharField(max_length=64, blank=True, null=True)
    
    class Meta:
        unique_together = ('object_type', 'field')    

class ModelAuditEvent(models.Model):    
    id = models.CharField(_('Access guid'), max_length=32, unique=True, default=make_uuid, primary_key=True) #primary_key override?
    
    object_type = models.ForeignKey(ContentType, verbose_name='Case linking content type', blank=True, null=True)
    object_uuid = models.CharField('object_uuid', max_length=32, db_index=True, blank=True, null=True)
    content_object = generic.GenericForeignKey('object_type', 'object_uuid')
    
    properties = models.ManyToManyField(FieldAccess, blank=True, null=True)
    property_data = models.TextField() #json of the actual fields accessed
    
    user = models.ForeignKey(User)
    accessed = models.DateTimeField(default = getdate())

import signals

from django.db import models
from django.contrib.auth.models import User
from domain.models import Domain


import os
import logging
import settings

# this is a really bad place for this class to live, but reference it here for now
from scheduler.fields import PickledObjectField

from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse


REQUEST_TYPES = (    
    ('GET', 'Get'),    
    ('POST', 'Post'),    
    ('PUT', 'Put'),    
)

class RequestLog(models.Model):
    '''Keeps track of incoming requests'''
    
    # Lots of stuff here is replicated in Submission.  
    # They should ultimately point here, but that's a data migration
    # problem.
    method = models.CharField(max_length=4, choices=REQUEST_TYPES)
    url = models.CharField(max_length=200)
    time = models.DateTimeField(_('Request Time'), default = datetime.now)
    ip = models.IPAddressField(_('Submitting IP Address'), null=True, blank=True)    
    is_secure = models.BooleanField(default=False)
    # The logged in user
    user = models.ForeignKey(User, null=True, blank=True)

    # Some pickled fields for having access to the raw info
    headers = PickledObjectField(_('Request Headers'))
    parameters = PickledObjectField(_('Request Parameters'))
    
    def __unicode__(self):
        return "%s to %s at %s from %s" % (self.method, self.url, 
                                           self.time, self.ip)
                
    @classmethod
    def from_request(cls, request):
        '''Creates an instance of a RequestLog from a standard
           django HttpRequest object.
        '''
        log = RequestLog() 
        log.method = request.method
        log.url = request.build_absolute_uri(request.path)
        log.time = datetime.now()
        log.is_secure = request.is_secure()
        if request.META.has_key('REMOTE_ADDR') and request.META['REMOTE_ADDR']:
            log.ip = request.META['REMOTE_ADDR']
        elif request.META.has_key('REMOTE_HOST') and request.META['REMOTE_HOST']:
            log.ip = request.META['REMOTE_HOST']
        # if request.user != User, then user is anonymous
        if isinstance(request.user, User):
            log.user = request.user
        
        def _convert_to_dict(obj):
            # converts a django-querydict to a true python dict
            # and converts any values to strings.  This could result
            # in a loss of information 
            to_return = {}
            for key, value in obj.items(): 
                to_return[key] = str(value)
            return to_return
        
        log.headers = _convert_to_dict(request.META)
        if request.method == "GET":
            log.parameters = _convert_to_dict(request.GET)
        else:
            log.parameters = _convert_to_dict(request.POST)
        return log
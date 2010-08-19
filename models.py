#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.utils.translation import ugettext_lazy as _
import datetime
import settings

#preliminary checks for settings variables

if not hasattr(settings, "LOGTRACKER_ALERT_EMAILS"):
    raise Exception("Error, Logtracker must have the property LOGTRACKER_ALERT_EMAILS as a list of emails in your settings file")

if not hasattr(settings, "LOGTRACKER_LOG_THRESHOLD"):
    raise Exception("Error, Logtracker must have an integer LOGTRACKER_LOG_THRESHOLD property in your settings file.")

if not hasattr(settings, "LOGTRACKER_ALERT_THRESHOLD"):
    raise Exception("Error, Logtracker must have an integer LOGTRACKER_ALERT_THRESHOLD property in your settings file.")


class LogTrack(models.Model):
    """
    LogTrack is a verbose means to store any arbitrary log information 
    into a python model.
    
    Using the admin.py as the way to instantiate the handler, all log messages 
    will be stored with all relevant data into the database.
    """        
    level = models.IntegerField(null=True)
    channel = models.CharField(max_length=128, null=True)
    created = models.DateTimeField(auto_now_add=True)
    message = models.TextField(null=True)    
    pathname = models.TextField(null=True)
    funcname = models.CharField(max_length=128,null=True)
    module = models.CharField(max_length=128,null=True)
    filename = models.CharField(max_length=128, null=True)
    line_no = models.IntegerField(null=True)    
    traceback = models.TextField(null=True)
    
    #when you do a logging message:
    #logging.debug('something interesting, extra={}
    #the extra kwarg should be a dictionary
    #anytime you add a new item to the extra dictionary, it will be assigned to the LogRecord 
    #object as a property
    #(just be careful to not use a reserved/in use LogRecord object
    #So, if you want to save some important local variable/state information for your error
    #it's easier to extract the information by finding  
    data_dump = models.TextField(null=True)
    
    def __unicode__(self):
        return self.message
    class Meta:
        verbose_name = _("Log Tracker")


import signals
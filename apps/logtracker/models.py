#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _
from reporters.models import Reporter, ReporterGroup

#log formatting
#Format     Description
#%(name)s     Name of the logger (logging channel).
#%(levelno)s     Numeric logging level for the message (DEBUG, INFO, WARNING, ERROR, CRITICAL).
#%(levelname)s     Text logging level for the message ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
#%(pathname)s     Full pathname of the source file where the logging call was issued (if available).
#%(filename)s     Filename portion of pathname.
#%(module)s     Module (name portion of filename).
#%(funcName)s     Name of function containing the logging call.
#%(lineno)d     Source line number where the logging call was issued (if available).
#%(created)f     Time when the LogRecord was created (as returned by time.time()).
#%(relativeCreated)d     Time in milliseconds when the LogRecord was created, relative to the time the logging module was loaded.
#%(asctime)s     Human-readable time when the LogRecord was created. By default this is of the form (the numbers after the comma are millisecond portion of the time).
#%(msecs)d     Millisecond portion of the time when the LogRecord was created.
#%(thread)d     Thread ID (if available).
#%(threadName)s     Thread name (if available).
#%(process)d     Process ID (if available).
#%(message)s     The logged message, computed as msg % args.

class LogTrack(models.Model):        
    level = models.IntegerField(null=True)
    channel = models.CharField(max_length=128, null=True)
    created = models.DateTimeField(null=True)
    message = models.TextField(null=True)    
    pathname = models.TextField(null=True)
    funcname = models.CharField(max_length=128,null=True)
    module = models.CharField(max_length=128,null=True)
    filename = models.CharField(max_length=128, null=True)
    line_no = models.IntegerField(null=True)    
    traceback = models.TextField(null=True)
    
    def __unicode__(self):
        return self.message
    class Meta:
        verbose_name = _("Log Tracker")
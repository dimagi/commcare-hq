#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
#modeled after the django-logging threaded handler
#http://code.google.com/p/django-logging

from logging import Handler
from logtracker.models import *

class TrackingHandler(Handler):
    """ Realtime log analysis handling for alerts. """   
    def __init__(self):
        Handler.__init__(self)

    def emit(self, record,  *args, **kwargs):
        """ Append the record to the buffer for the current thread. """
        newlog = LogTrack(level=record.levelno,
                          message=record.msg, 
                          filename=record.filename, 
                          line_no=record.lineno, 
                          pathname=record.pathname, 
                          funcname = record.funcName,
                          module = record.module)       
        newlog.save()
        
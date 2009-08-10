#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
#modeled after the django-logging threaded handler
#http://code.google.com/p/django-logging

from logging import Handler
from logtracker.models import *

logrecord_keys = ['msecs', 'args', 'name', 'thread', 'created', 'process', 'threadName', 'module', 'filename', 'levelno', 'processName', 'lineno', 'exc_info', 'exc_text', 'pathname', 'funcName', 'relativeCreated', 'levelname', 'msg']

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
                          module = record.module                                              
                          )
        #Simple reading of extras
        #data_dump=str(record.__dict__)
        
        #slightly more intelligent reading of extras
        record_dict = dict(record)
        if record_dict:
            for key in record_dict:
                if key in logrecord:
                    continue
                else:
                    if newlog.data_dump == None:
                        newlog.data_dump = ''
                    newlog.data_dump += key + ":=" + str(record_dict[key]) + "\n"
            newlog.save()
        
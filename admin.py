#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import datetime
import logging
import os
import re
import sys
import time
import datetime


import django
from logtracker.models import *
from logtracker.handlers import *

from django.contrib import admin

# Initialise and register the handler
handler = TrackingHandler()

#set the threshold in which the logs will be handled.
#in other words, we will only save logs with level > than what we set.
#for reference:
#CRITICAL = 50
#FATAL = CRITICAL
#ERROR = 40
#WARNING = 30
#WARN = WARNING
#INFO = 20
#DEBUG = 10
#NOTSET = 0

#the log_threshold is the ini value for what level the error handler should listen for
#if it's less than the threshold set, the handler will never trigger. 
logging.root.setLevel(int(settings.RAPIDSMS_APPS['logtracker']['log_threshold']))
logging.root.addHandler(handler)

class LogTrackAdmin(admin.ModelAdmin):
    list_display = ('id','level','channel','message','filename','line_no', 'data_dump')
    list_filter = ['level','channel','filename',]
    
admin.site.register(LogTrack,LogTrackAdmin)

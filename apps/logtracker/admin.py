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
logging.root.setLevel(logging.NOTSET)
logging.root.addHandler(handler)


class LogTrackAdmin(admin.ModelAdmin):
    list_display = ('id','level','channel','message','filename','line_no')
    list_filter = ['level','channel','filename',]    


admin.site.register(LogTrack,LogTrackAdmin)

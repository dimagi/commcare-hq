#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.contrib import admin
from corehq.apps.requestlogger.models import RequestLog

admin.site.register(RequestLog)
#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^docs/(?P<topic>\w+)$',  'docs.views.index', name='index'),
)

"""
URLpatterns for the debug toolbar. 

These should not be loaded explicitly; the debug toolbar middleware will patch
this into the urlconf for the request.
"""
from django.conf.urls.defaults import *
from django.conf import settings

_PREFIX = '__debug__'

urlpatterns = patterns('',
    url(r'^%s/couch_select/$' % _PREFIX, 'dimagi.utils.couch.couchdebugpanel.views.couch_select', name='couch_select'),
    url(r'^%s/couch_profile/$' % _PREFIX, 'dimagi.utils.couch.couchdebugpanel.views.couch_profile', name='couch_profile'),
)

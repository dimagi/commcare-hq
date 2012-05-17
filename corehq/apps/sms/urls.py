#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.sms.views',
    url(r'^post/?$', 'post', name='sms_post'),
    url(r'^send_to_recipients/$', 'send_to_recipients'),
    url(r'^compose/$', 'compose_message', name='sms_compose_message'),
    url(r'^$', 'messaging', name='messaging'),
)

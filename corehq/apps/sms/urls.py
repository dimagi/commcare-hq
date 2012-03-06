#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.sms.views',
    url(r'^post/?$', 'post', name='sms_post'),
    url(r'^send_to_recipients/$', 'send_to_recipients'),
    url(r'^$', 'messaging', name='messaging'),
    url(r'^tropo/$', 'tropo', name='tropo'),
)

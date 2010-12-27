#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.sms.views',
    url(r'/?$', 'messaging', name='messaging'),
)

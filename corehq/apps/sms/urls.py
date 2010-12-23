#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.sms.views',
    url(r'groups/?$', 'group_messaging', name='group_messaging'),
    url(r'users/?$', 'user_messaging', name='user_messaging'),
    url(r'/?$', 'messaging', name='messaging'),
)

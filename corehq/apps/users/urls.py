#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.users.views',
    (r'^$', 'users'),
    url(r'my_account$', 'my_account', name='my_account'),
    url(r'edit/(?P<user_id>[\w-]+)/?$', 'edit', name='edit_user'),
)
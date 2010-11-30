#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.users.views',
    (r'^$', 'users'),
    url(r'my_account$', 'my_account', name='my_account'),
    url(r'my_phone_numbers$', 'my_phone_numbers', name='my_phone_numbers'),
    url(r'my_commcare_accounts$', 'my_commcare_accounts', name='my_commcare_accounts'),
    url(r'edit/(?P<user_id>[\w-]+)/?$', 'edit', name='edit_user'),
    url(r'add/?$', 'add', name='add_user'),
    url(r'delete_phone_number/(?P<user_id>[\w-]+)/(?P<phone_number>[\w-]+)/?$', 
        'delete_phone_number', 
        name='delete_phone_number'),
)
#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.groups.views',
    url(r'add_group/?$', 
        'add_group',
        name='add_group'),
    url(r'delete_group/(?P<group_id>[\w-]+)/?$', 
        'delete_group',
        name='delete_group'),
    url(r'/?$', 'all_groups', name='all_groups'),
    url(r'mine/?$', 'my_groups', name='my_groups'),
)

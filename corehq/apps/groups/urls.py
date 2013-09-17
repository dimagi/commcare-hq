#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.groups.views',
    url(r'^add_group/$',
        'add_group',
        name='add_group'),
    url(r'^delete_group/(?P<group_id>[\w-]+)/$',
        'delete_group',
        name='delete_group'),
    url(r'^undo_delete_group/(?P<record_id>[\w-]+)/$',
        'undo_delete_group',
        name='undo_delete_group'),
    url(r'^edit_group/(?P<group_id>[\w-]+)/$',
        'edit_group',
        name='edit_group'),
    url(r'^update_group_data/(?P<group_id>[\w-]+)/$',
        'update_group_data',
        name='update_group_data'),
    url(r'^update_group_membership/(?P<group_id>[\w-]+)/$',
        'update_group_membership',
        name='update_group_membership'),
)

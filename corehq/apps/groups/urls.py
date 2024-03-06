from django.urls import re_path as url

from corehq.apps.groups.views import (
    add_group,
    delete_group,
    edit_group,
    restore_group,
    undo_delete_group,
    update_group_data,
    update_group_membership,
)

urlpatterns = [
    url(r'^add_group/$',
        add_group,
        name='add_group'),
    url(r'^delete_group/(?P<group_id>[\w-]+)/$',
        delete_group,
        name='delete_group'),
    url(r'^undo_delete_group/(?P<record_id>[\w-]+)/$',
        undo_delete_group,
        name='undo_delete_group'),
    url(r'^restore_group/(?P<group_id>[\w-]+)/$',
        restore_group,
        name='restore_group'),
    url(r'^edit_group/(?P<group_id>[\w-]+)/$',
        edit_group,
        name='edit_group'),
    url(r'^update_group_data/(?P<group_id>[\w-]+)/$',
        update_group_data,
        name='update_group_data'),
    url(r'^update_group_membership/(?P<group_id>[\w-]+)/$',
        update_group_membership,
        name='update_group_membership'),
]

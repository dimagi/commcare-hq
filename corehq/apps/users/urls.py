#from django.conf.urls.defaults import patterns, url
from corehq.apps.users.views.mobile.users import UploadCommCareUsers
from django.conf.urls.defaults import *
from corehq.apps.domain.utils import grandfathered_domain_re

urlpatterns = patterns('corehq.apps.users.views',
    url(r'^$', 'users', name="users_default"),
    #url(r'my_domains/$', 'my_domains', name='my_domains'),
    url(r'^change_my_password/$', 'change_my_password', name="change_my_password"),
    url(r'^change_password/(?P<login_id>[\w-]+)/$', 'change_password', name="change_password"),
    url(r'^account/(?P<couch_user_id>[\w-]+)/$', 'account', name='user_account'),
    url(r'^domain_accounts/(?P<couch_user_id>[\w-]+)/$', 'domain_accounts', name='domain_accounts'),
    url(r'^delete_phone_number/(?P<couch_user_id>[\w-]+)/$',
        'delete_phone_number',
        name='delete_phone_number'),
    url(r'^verify_phone_number/(?P<couch_user_id>[\w-]+)/$',
        'verify_phone_number',
        name='verify_phone_number'),
    url(r'^add_domain_membership/(?P<couch_user_id>[\w-]+)/(?P<domain_name>%s)/$' % grandfathered_domain_re,
        'add_domain_membership',
        name='add_domain_membership'),
    url(r'^delete_domain_membership/(?P<couch_user_id>[\w-]+)/(?P<domain_name>%s)/$' % grandfathered_domain_re,
        'delete_domain_membership',
        name='delete_domain_membership'),
    url(r'^web/remove/(?P<couch_user_id>[\w-]+)/$', 'remove_web_user', name='remove_web_user'),
    url(r'^web/undo_remove/(?P<record_id>[\w-]+)/$', 'undo_remove_web_user', name='undo_remove_web_user'),
    url(r'^web/invite/$', 'invite_web_user', name='invite_web_user'),
    url(r'^web/$', 'web_users', name='web_users'),
    url(r'^join/(?P<invitation_id>[\w-]+)/$', 'accept_invitation', name='domain_accept_invitation'),
    url(r'^web/role/$', 'post_user_role', name='post_user_role'),

    url(r'^httpdigest/?$', 'test_httpdigest'),

    url(r'^user_domain_transfer/(?P<prescription_id>[\w-]+)/$', 'user_domain_transfer', name='user_domain_transfer'),
    url(r'^audit_logs/$', 'audit_logs', name='user_audit_logs')
) + \
patterns("corehq.apps.users.views.mobile.users",
    url(r'^account/(?P<couch_user_id>[\w-]+)/user_data/$', 'update_user_data', name='update_user_data'),
    url(r'^commcare/$', 'base_view', name='commcare_users'),
    url(r'^commcare/list/$', 'user_list', name='user_list'),
    url(r'^commcare/archive/(?P<user_id>[\w-]+)/$', 'archive_commcare_user', name='archive_commcare_user'),
    url(r'^commcare/unarchive/(?P<user_id>[\w-]+)/$', 'archive_commcare_user', name='unarchive_commcare_user', kwargs={'is_active': True}),
    url(r'^commcare/delete/(?P<user_id>[\w-]+)/$', 'delete_commcare_user', name='delete_commcare_user'),
    url(r'^commcare/restore/(?P<user_id>[\w-]+)/$', 'restore_commcare_user', name='restore_commcare_user'),
    url(r'^commcare/upload/$', UploadCommCareUsers.as_view(), name='upload_commcare_users'),
    url(r'^commcare/download/$', 'download_commcare_users', name='download_commcare_users'),
    url(r'^commcare/set_group/$', 'set_commcare_user_group', name='set_commcare_user_group'),
    url(r'^add_commcare_account/$',
        'add_commcare_account',
        name='add_commcare_account'),
) +\
patterns("corehq.apps.users.views.mobile.groups",
    url(r'^group_memberships/(?P<couch_user_id>[\w-]+)/$', 'group_membership', name='group_membership'),
    url(r'^groups/$', 'all_groups', name='all_groups'),
    url(r'^groups/(?P<group_id>[ \w-]+)/$', 'group_members', name='group_members'),
)

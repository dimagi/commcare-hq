#from django.conf.urls.defaults import patterns, url
from corehq.apps.users.views import UploadCommCareUsers
from django.conf.urls.defaults import *
from corehq.apps.domain.utils import grandfathered_domain_re

urlpatterns = patterns('corehq.apps.users.views',
    url(r'^$', 'users', name="users_default"),
    #url(r'my_domains/$', 'my_domains', name='my_domains'),
    url(r'^change_my_password/$', 'change_my_password', name="change_my_password"),
    url(r'^change_password/(?P<login_id>[\w-]+)/$', 'change_password', name="change_password"),
    url(r'^account/(?P<couch_user_id>[\w-]+)/$', 'account', name='user_account'),
    url(r'^account/(?P<couch_user_id>[\w-]+)/user_data/$', 'update_user_data', name='update_user_data'),
    url(r'^account/(?P<couch_user_id>[\w-]+)/new_report_schedule/$', 'add_scheduled_report', name='add_scheduled_report'),
    url(r'^account/(?P<couch_user_id>[\w-]+)/delete_report_schedule/(?P<report_id>[\w-]+)/$', 'drop_scheduled_report', name='drop_scheduled_report'),
    url(r'^account/(?P<couch_user_id>[\w-]+)/test_report_schedule/(?P<report_id>[\w-]+)/$', 'test_scheduled_report', name='test_scheduled_report'),
    url(r'^domain_accounts/(?P<couch_user_id>[\w-]+)/$', 'domain_accounts', name='domain_accounts'),
    url(r'^delete_phone_number/(?P<couch_user_id>[\w-]+)/$',
        'delete_phone_number',
        name='delete_phone_number'),
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
    url(r'^join/(?P<invitation_id>[\w-]+)/$', 'accept_invitation', name='accept_invitation'),
    url(r'^web/role/$', 'post_user_role', name='post_user_role'),

    url(r'^commcare/$', 'commcare_users', name='commcare_users'),
    url(r'^commcare/archive/(?P<user_id>[\w-]+)/$', 'archive_commcare_user', name='archive_commcare_user'),
    url(r'^commcare/unarchive/(?P<user_id>[\w-]+)/$', 'archive_commcare_user', name='unarchive_commcare_user', kwargs={'is_active': True}),
    url(r'^commcare/delete/(?P<user_id>[\w-]+)/$', 'delete_commcare_user', name='delete_commcare_user'),
    url(r'^commcare/restore/(?P<user_id>[\w-]+)/$', 'restore_commcare_user', name='restore_commcare_user'),
    url(r'^commcare/upload/$', UploadCommCareUsers.as_view(), name='upload_commcare_users'),
    url(r'^commcare/upload-example/$', 'upload_commcare_users_example', name='upload_commcare_users_example'),
    url(r'^commcare/set_group/$', 'set_commcare_user_group', name='set_commcare_user_group'),

    url(r'^httpdigest/?$', 'test_httpdigest'),
    #url(r'my_groups/?$', 'my_groups', name='my_groups'),
    url(r'^group_memberships/(?P<couch_user_id>[\w-]+)/$', 'group_membership', name='group_membership'),
    url(r'^groups/$', 'all_groups', name='all_groups'),
    url(r'^groups/(?P<group_id>[ \w-]+)/$', 'group_members', name='group_members'),
    url(r'^add_commcare_account/$',
        'add_commcare_account',
        name='add_commcare_account'),

    url(r'^test_autocomplete/$', 'test_autocomplete'),
    url(r'^user_domain_transfer/(?P<prescription_id>[\w-]+)/$', 'user_domain_transfer', name='user_domain_transfer'),
    url(r'^audit_logs/$', 'audit_logs', name='user_audit_logs')
)

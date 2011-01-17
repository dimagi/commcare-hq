#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.domain.urls import domain_re

urlpatterns = patterns('corehq.apps.users.views',
    (r'^$', 'users'),
    #url(r'my_domains/$', 'my_domains', name='my_domains'),
    url(r'change_my_password/', 'change_my_password', name="change_my_password"),
    url(r'account/(?P<couch_user_id>[\w-]+)/?$', 'account', name='user_account'),
    url(r'domain_accounts/(?P<couch_user_id>[\w-]+)/?$', 'domain_accounts', name='domain_accounts'),
    url(r'delete_phone_number/(?P<couch_user_id>[\w-]+)/?$',
        'delete_phone_number',
        name='delete_phone_number'),
    url(r'add_domain_membership/(?P<couch_user_id>[\w-]+)/(?P<domain_name>%s)/?$' % domain_re,
        'add_domain_membership',
        name='add_domain_membership'),
    url(r'delete_domain_membership/(?P<couch_user_id>[\w-]+)/(?P<domain_name>%s)/?$' % domain_re,
        'delete_domain_membership',
        name='delete_domain_membership'),
    url(r'unlink_commcare_account/(?P<couch_user_id>[\w-]+)/(?P<commcare_user_index>[\d-]+)/?$',
        'unlink_commcare_account',
        name='unlink_commcare_account'),
    url(r'link_commcare_account/(?P<couch_user_id>[\w-]+)/(?P<commcare_login_id>[\w-]+)/?$',
        'link_commcare_account_to_user',
        name='link_commcare_account_to_user'),
    url(r'web/create/$', 'create_web_user', name='create_web_user'),
    url(r'web/$', 'web_users', name='web_users'),


    url(r'commcare/?$', 'commcare_users', name='commcare_users'),
    url(r'^httpdigest/?$', 'httpdigest'),
    #url(r'my_groups/?$', 'my_groups', name='my_groups'),
    url(r'group_memberships/(?P<couch_user_id>[\w-]+)/?$', 'group_membership', name='group_membership'),
    url(r'group_members/(?P<group_name>[ \w-]+)/?$', 'group_members', name='group_members'),
    url(r'all_groups/?$', 'all_groups', name='all_groups'),
    url(r'add_commcare_account/?$', 
        'add_commcare_account',
        name='add_commcare_account'),

    url(r'test_autocomplete', 'test_autocomplete'),
)

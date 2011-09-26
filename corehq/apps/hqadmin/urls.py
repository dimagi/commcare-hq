from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqadmin.views',
    (r'^$', 'default'),
    url(r'^domains/$', 'domain_list', name="domain_list"),
    url(r'^users/$', 'active_users', name="active_users"),
    url(r'^commcare_version/$', 'commcare_version_report', name='commcare_version_report'),
)
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqadmin.views',
    (r'^$', 'default'),
    url(r'^global/$', 'global_report', name="global"),
    url(r'^domains/$', 'domain_list', name="domain_list"),
    url(r'^users/$', 'active_users', name="active_users"),
    url(r'^commcare_version/$', 'commcare_version_report', name='commcare_version_report'),
    url(r'^domain_activity/$', 'domain_activity_report', name='domain_activity_report'),
    url(r'^message_logs/$', 'message_log_report', name='message_log_report'),
)
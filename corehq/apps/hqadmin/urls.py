from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqadmin.views',
    url(r'^$', 'default', name="default_admin_report"),
    url(r'^global/$', 'global_report', name="global_report"),
    url(r'^domains/$', 'domain_list', name="domain_list"),
    url(r'^users/$', 'active_users', name="active_users"),
    url(r'^commcare_version/$', 'commcare_version_report', name='commcare_version_report'),
    url(r'^domain_activity/$', 'domain_activity_report', name='domain_activity_report'),
    url(r'^message_logs/$', 'message_log_report', name='message_log_report'),
    url(r'^emails/$', 'emails', name='global_email_list'),
    url(r'^submissions_errors/$', 'submissions_errors', name='global_submissions_errors'),
)
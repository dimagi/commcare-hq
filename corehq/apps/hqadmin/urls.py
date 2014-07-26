from django.conf.urls.defaults import *
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from .views import FlagBrokenBuilds

urlpatterns = patterns('corehq.apps.hqadmin.views',
    url(r'^$', 'default', name="default_admin_report"),
    url(r'^export/global/$', 'global_report', name="export_global_report", kwargs=dict(as_export=True)),
    url(r'^global/$', 'global_report', name="global_report"),
    url(r'^system/$', 'system_info', name="system_info"),
    url(r'^user_reports/$', 'mobile_user_reports', name='mobile_user_reports'),
    url(r'^system/download_recent_changes', 'download_recent_changes', name="download_recent_changes"),
    url(r'^system/system_ajax$', 'system_ajax', name="system_ajax"),
    url(r'^users/$', 'active_users', name="active_users"),
    url(r'^commcare_version/$', 'commcare_version_report', name='commcare_version_report'),
    url(r'^domain_activity/$', 'domain_activity_report', name='domain_activity_report'),
    url(r'^message_logs/$', 'message_log_report', name='message_log_report'),
    url(r'^emails/$', 'emails', name='global_email_list'),
    url(r'^submissions_errors/$', 'submissions_errors', name='global_submissions_errors'),
    url(r'^domains/update/$', 'update_domains', name="domain_update"),
    url(r'^mass_email/$', 'mass_email', name="mass_email"),
    url(r'^domains/download/$', 'domain_list_download', name="domain_list_download"),
    url(r'^noneulized_users/$', 'noneulized_users', name="noneulized_users"),
    url(r'^commcare_settings/$', 'all_commcare_settings', name="all_commcare_settings"),
    url(r'^broken_suite_files/$', 'find_broken_suite_files', name="find_broken_suite_files"),
    url(r'^management_commands/$', 'management_commands', name="management_commands"),
    url(r'^run_command/$', 'run_command', name="run_management_command"),
    url(r'^phone/restore/$', 'admin_restore', name="admin_restore"),
    url(r'^flag_broken_builds/$', FlagBrokenBuilds.as_view(), name="flag_broken_builds"),
    url(r'^stats_data/$', 'stats_data', name="admin_stats_data"),
    url(r'^loadtest/$', 'loadtest', name="loadtest_report"),
    url(r'^reset_pillow_checkpoint/$', 'reset_pillow_checkpoint', name="reset_pillow_checkpoint"),

    AdminReportDispatcher.url_pattern(),
)

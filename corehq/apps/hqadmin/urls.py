from django.conf.urls import *
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from .views import FlagBrokenBuilds, AuthenticateAs

from corehq.apps.api.urls import admin_urlpatterns as admin_api_urlpatterns

urlpatterns = patterns('corehq.apps.hqadmin.views',
    url(r'^$', 'default', name="default_admin_report"),
    url(r'^system/$', 'system_info', name="system_info"),
    url(r'^system/recent_changes/$', 'view_recent_changes', name="view_recent_changes"),
    url(r'^system/recent_changes/download/$', 'download_recent_changes', name="download_recent_changes"),
    url(r'^system/system_ajax$', 'system_ajax', name="system_ajax"),
    url(r'^system/db_comparisons', 'db_comparisons', name="db_comparisons"),
    url(r'^users/$', 'active_users', name="active_users"),
    url(r'^commcare_version/$', 'commcare_version_report', name='commcare_version_report'),
    url(r'^message_logs/$', 'message_log_report', name='message_log_report'),
    url(r'^contact_email/$', 'contact_email', name="contact_email"),
    url(r'^mass_email/$', 'mass_email', name="mass_email"),
    url(r'^auth_as/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/(?P<domain>{})/$'.format(new_domain_re),
        AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^noneulized_users/$', 'noneulized_users', name="noneulized_users"),
    url(r'^commcare_settings/$', 'all_commcare_settings', name="all_commcare_settings"),
    url(r'^management_commands/$', 'management_commands', name="management_commands"),
    url(r'^run_command/$', 'run_command', name="run_management_command"),
    url(r'^phone/restore/$', 'admin_restore', name="admin_restore"),
    url(r'^flag_broken_builds/$', FlagBrokenBuilds.as_view(), name="flag_broken_builds"),
    url(r'^stats_data/$', 'stats_data', name="admin_stats_data"),
    url(r'^admin_reports_stats_data/$', 'admin_reports_stats_data', name="admin_reports_stats_data"),
    url(r'^loadtest/$', 'loadtest', name="loadtest_report"),
    url(r'^reset_pillow_checkpoint/$', 'reset_pillow_checkpoint', name="reset_pillow_checkpoint"),
    url(r'^doc_in_es/$', 'doc_in_es', name='doc_in_es'),
    url(r'^callcenter_test/$', 'callcenter_test', name='callcenter_test'),
    (r'^api/', include(admin_api_urlpatterns)),

    AdminReportDispatcher.url_pattern(),
)

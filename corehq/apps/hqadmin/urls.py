from django.conf.urls import *
from django.views.generic import TemplateView
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from .views import FlagBrokenBuilds, AuthenticateAs, SystemInfoView

from corehq.apps.api.urls import admin_urlpatterns as admin_api_urlpatterns

urlpatterns = patterns('corehq.apps.hqadmin.views',
    url(r'^$', 'default', name="default_admin_report"),
    url(r'^system/$', SystemInfoView.as_view(), name=SystemInfoView.urlname),
    url(r'^system/recent_changes/$', 'view_recent_changes', name="view_recent_changes"),
    url(r'^system/recent_changes/download/$', 'download_recent_changes', name="download_recent_changes"),
    url(r'^system/system_ajax$', 'system_ajax', name="system_ajax"),
    url(r'^contact_email/$', 'contact_email', name="contact_email"),
    url(r'^mass_email/$', 'mass_email', name="mass_email"),
    url(r'^auth_as/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/(?P<domain>{})/$'.format(new_domain_re),
        AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^commcare_settings/$', 'all_commcare_settings', name="all_commcare_settings"),
    url(r'^management_commands/$', 'management_commands', name="management_commands"),
    url(r'^run_command/$', 'run_command', name="run_management_command"),
    url(r'^phone/restore/$', 'admin_restore', name="admin_restore"),
    url(r'^flag_broken_builds/$', FlagBrokenBuilds.as_view(), name="flag_broken_builds"),
    url(r'^stats_data/$', 'stats_data', name="admin_stats_data"),
    url(r'^admin_reports_stats_data/$', 'admin_reports_stats_data', name="admin_reports_stats_data"),
    url(r'^loadtest/$', 'loadtest', name="loadtest_report"),
    url(r'^do_pillow_op/$', 'pillow_operation_api', name="pillow_operation_api"),
    url(r'^doc_in_es/$', 'doc_in_es', name='doc_in_es'),
    url(r'^raw_couch/$', 'raw_couch', name='raw_couch'),
    url(r'^callcenter_test/$', 'callcenter_test', name='callcenter_test'),
    (r'^api/', include(admin_api_urlpatterns)),
    url(r'^download_malt/$', 'malt_as_csv', name='download_malt'),
    url(r'^dimagisphere/$',
        require_superuser(TemplateView.as_view(template_name='hqadmin/dimagisphere/form_map.html')),
        name='dimagisphere'),
    url(r'^dimagisphere/charts$',
        require_superuser(TemplateView.as_view(template_name='hqadmin/dimagisphere/form_feed.html')),
        name='dimagisphere_charts'),
    AdminReportDispatcher.url_pattern(),
)

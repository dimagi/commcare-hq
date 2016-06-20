from django.conf.urls import *
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.hqadmin.views import AdminRestoreView
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from .views import (
    FlagBrokenBuilds, AuthenticateAs, SystemInfoView,
    DownloadMALTView,
    RecentCouchChangesView,
    ManagementCommandsView,
    CallcenterUCRCheck,
    DimagisphereView)

from corehq.apps.api.urls import admin_urlpatterns as admin_api_urlpatterns

urlpatterns = patterns('corehq.apps.hqadmin.views',
    url(r'^$', 'default', name="default_admin_report"),
    url(r'^system/$', SystemInfoView.as_view(), name=SystemInfoView.urlname),
    url(r'^system/recent_changes/$', RecentCouchChangesView.as_view(),
        name=RecentCouchChangesView.urlname),
    url(r'^system/recent_changes/download/$', 'download_recent_changes', name="download_recent_changes"),
    url(r'^system/system_ajax$', 'system_ajax', name="system_ajax"),
    url(r'^system/check_services$', 'check_services', name="check_services"),
    url(r'^system/autostaging/$', 'branches_on_staging', name="branches_on_staging"),
    url(r'^auth_as/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/(?P<domain>{})/$'.format(new_domain_re),
        AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^management_commands/$', ManagementCommandsView.as_view(),
        name=ManagementCommandsView.urlname),
    url(r'^run_command/$', 'run_command', name="run_management_command"),
    url(r'^phone/restore/$', AdminRestoreView.as_view(), name="admin_restore"),
    url(r'^phone/restore/(?P<app_id>[\w-]+)/$', AdminRestoreView.as_view(), name='app_aware_admin_restore'),
    url(r'^flag_broken_builds/$', FlagBrokenBuilds.as_view(), name="flag_broken_builds"),
    url(r'^stats_data/$', 'stats_data', name="admin_stats_data"),
    url(r'^admin_reports_stats_data/$', 'admin_reports_stats_data', name="admin_reports_stats_data"),
    url(r'^do_pillow_op/$', 'pillow_operation_api', name="pillow_operation_api"),
    url(r'^web_user_lookup/$', 'web_user_lookup', name='web_user_lookup'),
    url(r'^doc_in_es/$', 'doc_in_es', name='doc_in_es'),
    url(r'^raw_couch/$', 'raw_couch', name='raw_couch'),
    url(r'^raw_doc/$', 'raw_doc', name='raw_doc'),
    url(r'^callcenter_test/$', 'callcenter_test', name='callcenter_test'),
    (r'^api/', include(admin_api_urlpatterns)),
    url(r'^callcenter_ucr_check/$', CallcenterUCRCheck.as_view(), name=CallcenterUCRCheck.urlname),
    (r'^api/', include(admin_api_urlpatterns)),
    url(r'^download_malt/$',
        DownloadMALTView.as_view(), name=DownloadMALTView.urlname),
    url(r'^dimagisphere/$',
        require_superuser(DimagisphereView.as_view(template_name='hqadmin/dimagisphere/form_feed.html')),
        name='dimagisphere'),
    AdminReportDispatcher.url_pattern(),
)

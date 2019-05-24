from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

from corehq.apps.api.urls import admin_urlpatterns as admin_api_urlpatterns
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.hqadmin.views.data import doc_in_es, raw_doc
from corehq.apps.hqadmin.views.operations import (
    CallcenterUCRCheck,
    ReprocessMessagingCaseUpdatesView,
    mass_email,
)
from corehq.apps.hqadmin.views.reports import (
    DimagisphereView,
    DownloadGIRView,
    DownloadMALTView,
    admin_reports_stats_data,
    stats_data,
    top_five_projects_by_country,
)
from corehq.apps.hqadmin.views.system import (
    RecentCouchChangesView,
    SystemInfoView,
    branches_on_staging,
    check_services,
    download_recent_changes,
    pillow_operation_api,
    system_ajax,
)
from corehq.apps.hqadmin.views.users import (
    AdminRestoreView,
    AppBuildTimingsView,
    AuthenticateAs,
    DisableTwoFactorView,
    DisableUserView,
    SuperuserManagement,
    WebUserDataView,
    web_user_lookup,
)
from corehq.apps.hqadmin.views.utils import default
from corehq.apps.reports.dispatcher import AdminReportDispatcher

urlpatterns = [
    url(r'^$', default, name="default_admin_report"),
    url(r'^system/$', SystemInfoView.as_view(), name=SystemInfoView.urlname),
    url(r'^system/recent_changes/$', RecentCouchChangesView.as_view(),
        name=RecentCouchChangesView.urlname),
    url(r'^system/recent_changes/download/$', download_recent_changes, name="download_recent_changes"),
    url(r'^system/system_ajax$', system_ajax, name="system_ajax"),
    url(r'^system/check_services$', check_services, name="check_services"),
    url(r'^system/autostaging/$', branches_on_staging, name="branches_on_staging"),
    url(r'^mass_email/$', mass_email, name="mass_email"),
    # Same view supported with three possible urls to support tracking
    # username and domain in the url via audit
    url(r'^auth_as/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/$', AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^auth_as/(?P<username>[^/]*)/(?P<domain>{})/$'.format(new_domain_re),
        AuthenticateAs.as_view(), name=AuthenticateAs.urlname),
    url(r'^superuser_management/$', SuperuserManagement.as_view(), name=SuperuserManagement.urlname),
    url(r'^phone/restore/$', AdminRestoreView.as_view(), name="admin_restore"),
    url(r'^phone/restore/(?P<app_id>[\w-]+)/$', AdminRestoreView.as_view(), name='app_aware_admin_restore'),
    url(r'^app_build_timings/$', AppBuildTimingsView.as_view(), name="app_build_timings"),
    url(r'^stats_data/$', stats_data, name="admin_stats_data"),
    url(r'^admin_reports_stats_data/$', admin_reports_stats_data, name="admin_reports_stats_data"),
    url(r'^do_pillow_op/$', pillow_operation_api, name="pillow_operation_api"),
    url(r'^web_user_lookup/$', web_user_lookup, name='web_user_lookup'),
    url(r'^disable_two_factor/$', DisableTwoFactorView.as_view(), name=DisableTwoFactorView.urlname),
    url(r'^disable_account/$', DisableUserView.as_view(), name=DisableUserView.urlname),
    url(r'^doc_in_es/$', doc_in_es, name='doc_in_es'),
    url(r'^raw_couch/$', raw_doc, name='raw_couch'),
    url(r'^raw_doc/$', raw_doc, name='raw_doc'),
    url(r'^api/', include(admin_api_urlpatterns)),
    url(r'^callcenter_ucr_check/$', CallcenterUCRCheck.as_view(), name=CallcenterUCRCheck.urlname),
    url(r'^download_malt/$',
        DownloadMALTView.as_view(), name=DownloadMALTView.urlname),
    url(r'^download_gir', DownloadGIRView.as_view(), name=DownloadGIRView.urlname),
    url(r'^dimagisphere/$',
        require_superuser(DimagisphereView.as_view(template_name='hqadmin/dimagisphere/form_feed.html')),
        name='dimagisphere'),
    url(r'^reprocess_messaging_case_updates/$', ReprocessMessagingCaseUpdatesView.as_view(),
        name=ReprocessMessagingCaseUpdatesView.urlname),
    url(r'^top_five_projects_by_country/$', top_five_projects_by_country, name='top_five_projects_by_country'),
    url(r'^web_user_data', WebUserDataView.as_view(), name=WebUserDataView.urlname),
    AdminReportDispatcher.url_pattern(),
]

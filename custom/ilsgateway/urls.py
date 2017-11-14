from __future__ import absolute_import
from django.conf.urls import url, include

from corehq.apps.api.urls import CommCareHqApi
from custom.ilsgateway.resources.v0_1 import ILSLocationResource
from custom.ilsgateway.slab.views import SLABConfigurationView, SLABEditLocationView
from custom.ilsgateway.views import (
    SupervisionDocumentListView, SupervisionDocumentDeleteView,
    SupervisionDocumentView, ReportRunListView,
    ReportRunDeleteView, DashboardPageRedirect, GlobalStats,
    PendingRecalculationsListView, run_warehouse_runner,
    end_report_run, save_ils_note,
    recalculate_moshi_rural, recalculate_non_facilities,
)
from custom.ilsgateway.views import ILSConfigView

hq_api = CommCareHqApi(api_name='v0.3')
hq_api.register(ILSLocationResource())

urlpatterns = [
    url(r'^ils_dashboard_report/$', DashboardPageRedirect.as_view(permanent=True), name='ils_dashboard_report'),
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname),
    url(r'^run_reports/$', run_warehouse_runner, name='run_reports'),
    url(r'^end_report_run/$', end_report_run, name='end_report_run'),
    url(r'^supervision/$', SupervisionDocumentListView.as_view(), name=SupervisionDocumentListView.urlname),
    url(r'^delete_supervision_document/(?P<document_id>\d+)/$', SupervisionDocumentDeleteView.as_view(),
        name='delete_supervision_document'),
    url(r'^supervision/(?P<document_id>\d+)/$', SupervisionDocumentView.as_view(), name='supervision_document'),
    url(r'^save_ils_note/$', save_ils_note, name='save_ils_note'),
    url(r'^report_runs/(?P<pk>\d+)/delete/$', ReportRunDeleteView.as_view(), name='delete_report_run'),
    url(r'^report_runs/$', ReportRunListView.as_view(), name='report_run_list'),
    url(r'^recalculations/$', PendingRecalculationsListView.as_view(), name='recalculations'),
    url(r'^slab_configuration/$', SLABConfigurationView.as_view(), name='slab_configuration'),
    url(r'^slab_edit_location/(?P<location_id>[\w-]+)', SLABEditLocationView.as_view(), name='slab_edit_location'),
    # one-off
    url(r'^recalculate_moshi/$', recalculate_moshi_rural, name='recalculate_moshi_rural'),
    url(r'^recalculate_non_facilities/$', recalculate_non_facilities, name='recalculate_non_facilities'),
    # api
    url(r'^', include(hq_api.urls)),
]

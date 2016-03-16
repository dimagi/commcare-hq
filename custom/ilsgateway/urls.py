from django.conf.urls import patterns, url

from custom.ilsgateway.views import SupervisionDocumentListView, SupervisionDocumentDeleteView, \
    SupervisionDocumentView, ReportRunListView, ReportRunDeleteView, DashboardPageRedirect, GlobalStats
from custom.ilsgateway.views import ILSConfigView

urlpatterns = patterns('custom.ilsgateway.views',
    url(r'^ils_dashboard_report/$', DashboardPageRedirect.as_view(), name='ils_dashboard_report'),
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname),
    url(r'^run_reports/$', 'run_warehouse_runner', name='run_reports'),
    url(r'^end_report_run/$', 'end_report_run', name='end_report_run'),
    url(r'^supervision/$', SupervisionDocumentListView.as_view(), name=SupervisionDocumentListView.urlname),
    url(r'^delete_supervision_document/(?P<document_id>\d+)/$', SupervisionDocumentDeleteView.as_view(),
        name='delete_supervision_document'),
    url(r'^supervision/(?P<document_id>\d+)/$', SupervisionDocumentView.as_view(), name='supervision_document'),
    url(r'^save_ils_note/$', 'save_ils_note', name='save_ils_note'),
    url(r'^report_runs/(?P<pk>\d+)/delete/$', ReportRunDeleteView.as_view(), name='delete_report_run'),
    url(r'^report_runs/$', ReportRunListView.as_view(), name='report_run_list'),
)

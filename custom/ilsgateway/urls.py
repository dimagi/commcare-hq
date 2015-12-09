from django.conf.urls import patterns, url
from custom.ilsgateway.views import GlobalStats, SupervisionDocumentListView, SupervisionDocumentDeleteView, \
    SupervisionDocumentView, ReportRunListView, ReportRunDeleteView, ProductAvailabilityDeleteView
from custom.ilsgateway.views import ILSConfigView

urlpatterns = patterns('custom.ilsgateway.views',
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^sync_ilsgateway/$', 'sync_ilsgateway', name='sync_ilsgateway'),
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname),
    # for testing purposes

    url(r'^ils_sync_stock_data/$', 'ils_sync_stock_data', name='ils_sync_stock_data'),
    url(r'^ils_clear_stock_data/$', 'ils_clear_stock_data', name='ils_clear_stock_data'),

    url(r'^run_reports/$', 'run_warehouse_runner', name='run_reports'),
    url(r'^end_report_run/$', 'end_report_run', name='end_report_run'),
    url(r'^ils_resync_web_users/$', 'ils_resync_web_users', name='ils_resync_web_users'),
    url(r'^delete_runs/$', 'delete_reports_runs', name='delete_runs'),
    url(r'^supervision/$', SupervisionDocumentListView.as_view(), name=SupervisionDocumentListView.urlname),
    url(r'^delete_supervision_document/(?P<document_id>\d+)/$', SupervisionDocumentDeleteView.as_view(),
        name='delete_supervision_document'),
    url(r'^supervision/(?P<document_id>\d+)/$', SupervisionDocumentView.as_view(), name='supervision_document'),
    url(r'^save_ils_note/$', 'save_ils_note', name='save_ils_note'),
    url(r'^fix_groups_in_location/$', 'fix_groups_in_location', name='fix_groups_in_location'),
    url(r'^change_date/$', 'change_runner_date_to_last_migration', name='change_runner_date_to_last_migration'),
    url(r'^report_runs/(?P<pk>\d+)/delete/$', ReportRunDeleteView.as_view(), name='delete_report_run'),
    url(r'^report_runs/$', ReportRunListView.as_view(), name='report_run_list'),
    url(
        r'^product_availability/(?P<pk>\d+)/delete/$',
        ProductAvailabilityDeleteView.as_view(),
        name='product_availability_delete'
    ),
    url(r'^fix_stock_data/$', 'fix_stock_data_view', name='fix_stock_data')
)

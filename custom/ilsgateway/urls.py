from django.conf.urls import patterns, url
from custom.ilsgateway.views import GlobalStats
from custom.ilsgateway.views import ILSConfigView

urlpatterns = patterns('custom.ilsgateway.views',
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^sync_ilsgateway/$', 'sync_ilsgateway', name='sync_ilsgateway'),
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname),
    # for testing purposes

    url(r'^ils_sync_stock_data/$', 'ils_sync_stock_data', name='ils_sync_stock_data'),
    url(r'^ils_clear_stock_data/$', 'ils_clear_stock_data', name='ils_clear_stock_data'),

    url(r'^run_reports/$', 'run_warehouse_runner', name='run_reports'),
    url(r'^end_report_run/$', 'end_report_run', name='end_report_run')
)

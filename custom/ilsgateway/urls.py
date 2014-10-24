from django.conf.urls import patterns, url
from custom.ilsgateway.views import GlobalStats
from custom.ilsgateway.views import ILSConfigView

urlpatterns = patterns('custom.ilsgateway.views',
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^sync_ilsgateway/$', 'sync_ilsgateway', name='sync_ilsgateway'),
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname),
    # for testing purposes
    url(r'^sync_stock_data/$', 'sync_stock_data', name='sync_stock_data'),
    url(r'^run_reports/$', 'run_warehouse_runner', name='run_reports')
)

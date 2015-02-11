from django.conf.urls import patterns, url
from custom.ewsghana.views import EWSConfigView, EWSGlobalStats

urlpatterns = patterns('custom.ewsghana.views',
    url(r'^ews_config/$', EWSConfigView.as_view(), name=EWSConfigView.urlname),
    url(r'^sync_ewsghana/$', 'sync_ewsghana', name='sync_ewsghana'),
    url(r'^global_stats/$', EWSGlobalStats.as_view(), name=EWSGlobalStats.urlname),
    # for testing purposes

    url(r'^ews_sync_stock_data/$', 'ews_sync_stock_data', name='ews_sync_stock_data'),
    url(r'^ews_clear_stock_data/$', 'ews_clear_stock_data', name='ews_clear_stock_data'),
    url(r'^ews_fix_languages/$', 'ews_fix_languages', name='ews_fix_languages'),
    url(r'^inventory_managment/$', 'inventory_management', name='inventory_managment')
)

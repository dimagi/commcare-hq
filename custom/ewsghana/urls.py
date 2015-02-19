from django.conf.urls import patterns, url
from custom.ewsghana.views import EWSConfigView, EWSGlobalStats

urlpatterns = patterns('custom.ewsghana.views',
    url(r'^ews_config/$', EWSConfigView.as_view(), name=EWSConfigView.urlname),
    url(r'^sync_ewsghana/$', 'sync_ewsghana', name='sync_ewsghana'),
    url(r'^global_stats/$', EWSGlobalStats.as_view(), name=EWSGlobalStats.urlname),
    # for testing purposes

    url(r'^ews_sync_stock_data/$', 'ews_sync_stock_data', name='ews_sync_stock_data'),
    url(r'^ews_clear_stock_data/$', 'ews_clear_stock_data', name='ews_clear_stock_data'),
    url(r'^ews_fix_languages/$', 'ews_fix_sms_users', name='ews_fix_sms_users'),
    url(r'^ews_fix_locations/$', 'ews_fix_locations', name='ews_fix_locations'),
    url(r'^ews_add_products_to_locs/$', 'ews_add_products_to_locs', name='ews_add_products_to_locs'),
    url(r'^clear_products/$', 'clear_products', name='clear_products'),
    url(r'^inventory_managment/$', 'inventory_management', name='inventory_managment')
)

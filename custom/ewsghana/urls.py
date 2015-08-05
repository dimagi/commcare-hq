from django.conf.urls import patterns, url, include
from corehq.apps.api.urls import CommCareHqApi
from custom.ewsghana.resources.v0_1 import EWSLocationResource
from custom.ewsghana.views import EWSConfigView, EWSGlobalStats, RemindersTester, InputStockView

hq_api = CommCareHqApi(api_name='v0.3')
hq_api.register(EWSLocationResource())

urlpatterns = patterns('custom.ewsghana.views',
    url(r'^ews_config/$', EWSConfigView.as_view(), name=EWSConfigView.urlname),
    url(r'^sync_ewsghana/$', 'sync_ewsghana', name='sync_ewsghana'),
    url(r'^global_stats/$', EWSGlobalStats.as_view(), name=EWSGlobalStats.urlname),
    # for testing purposes

    url(r'^ews_sync_stock_data/$', 'ews_sync_stock_data', name='ews_sync_stock_data'),
    url(r'^ews_clear_stock_data/$', 'ews_clear_stock_data', name='ews_clear_stock_data'),
    url(r'^configure_in_charge/$', 'configure_in_charge', name='configure_in_charge'),
    url(r'^ews_resync_web_users/$', 'ews_resync_web_users', name='ews_resync_web_users'),
    url(r'^inventory_managment/$', 'inventory_management', name='inventory_managment'),
    url(r'^stockouts_product/$', 'stockouts_product', name='stockouts_product'),
    url(r'^reminder_test/(?P<phone_number>\d+)/$', RemindersTester.as_view(), name='reminders_tester'),
    url(r'^ews_fix_locations/$', 'ews_fix_locations', name='ews_fix_locations'),
    url(r'^ews_add_products_to_locs/$', 'ews_add_products_to_locs', name='ews_add_products_to_locs'),
    url(r'^clear_products/$', 'clear_products', name='clear_products'),
    url(r'^delete_last_stock_data/$', 'delete_last_stock_data', name='delete_last_stock_data'),
    url(r'^(?P<site_code>\w+)/input_stock/$', InputStockView.as_view(), name='input_stock'),
    url(r'^', include(hq_api.urls)),
    url(r'^convert_user_data_fields/$', 'convert_user_data_fields', name='convert_user_data_fields')
)

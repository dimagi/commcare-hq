from django.conf.urls import patterns, url, include
from corehq.apps.api.urls import CommCareHqApi
from custom.ewsghana.resources.v0_1 import EWSLocationResource
from custom.ewsghana.views import EWSConfigView, EWSGlobalStats, InputStockView, EWSUserExtensionView, \
    BalanceMigrationView, DashboardPageView, BalanceEmailMigrationView

hq_api = CommCareHqApi(api_name='v0.3')
hq_api.register(EWSLocationResource())

urlpatterns = patterns('custom.ewsghana.views',
    url(r'^ews_config/$', EWSConfigView.as_view(), name=EWSConfigView.urlname),
    url(r'^sync_ewsghana/$', 'sync_ewsghana', name='sync_ewsghana'),
    url(r'^global_stats/$', EWSGlobalStats.as_view(), name=EWSGlobalStats.urlname),
    url(r'^balance_email_reports_migration/$', 'balance_email_reports_migration',
        name='balance_email_reports_migration'),

    url(r'^ews_sync_stock_data/$', 'ews_sync_stock_data', name='ews_sync_stock_data'),
    url(r'^ews_clear_stock_data/$', 'ews_clear_stock_data', name='ews_clear_stock_data'),
    url(r'^configure_in_charge/$', 'configure_in_charge', name='configure_in_charge'),
    url(r'^ews_resync_web_users/$', 'ews_resync_web_users', name='ews_resync_web_users'),
    url(r'^inventory_managment/$', 'inventory_management', name='inventory_managment'),
    url(r'^stockouts_product/$', 'stockouts_product', name='stockouts_product'),
    url(r'^ews_fix_locations/$', 'ews_fix_locations', name='ews_fix_locations'),
    url(r'^ews_add_products_to_locs/$', 'ews_add_products_to_locs', name='ews_add_products_to_locs'),
    url(r'^migrate_email_settings/$', 'migrate_email_settings_view', name='migrate_email_settings'),
    url(r'^migrate_needs_reminders_field/$', 'delete_connections_field',
        name='delete_connections_field'),
    url(r'^delete_last_stock_data/$', 'delete_last_stock_data', name='delete_last_stock_data'),
    url(r'^(?P<site_code>\w+)/input_stock/$', InputStockView.as_view(), name='input_stock'),
    url(r'^', include(hq_api.urls)),
    url(r'^convert_user_data_fields/$', 'convert_user_data_fields', name='convert_user_data_fields'),
    url(r'^non_administrative_locations/$', 'non_administrative_locations_for_select2'),
    url(r'^user_settings/(?P<user_id>[ \w-]+)/$', EWSUserExtensionView.as_view(), name='ews_user_settings'),
    url(r'^dashboard_page/$', DashboardPageView.as_view(), name='dashboard_page'),
    url(r'^balance/$', BalanceMigrationView.as_view(), name='balance_migration'),
    url(r'^email_balance/$', BalanceEmailMigrationView.as_view(), name='email_balance_migration')
)

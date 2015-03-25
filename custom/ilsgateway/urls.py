from django.conf.urls import patterns, url
from custom.ilsgateway.views import GlobalStats, SupervisionDocumentListView, SupervisionDocumentDeleteView, \
    SupervisionDocumentView, RemindersTester
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
    url(r'^ils_sms_users_fix/$', 'ils_sms_users_fix', name='ils_sms_users_fix'),
    url(r'^delete_runs/$', 'delete_reports_runs', name='delete_runs'),
    url(r'^supervision/$', SupervisionDocumentListView.as_view(), name=SupervisionDocumentListView.urlname),
    url(r'^delete_supervision_document/(?P<document_id>\d+)/$', SupervisionDocumentDeleteView.as_view(),
        name='delete_supervision_document'),
    url(r'^supervision/(?P<document_id>\d+)/$', SupervisionDocumentView.as_view(), name='supervision_document'),
    url(r'^reminder_test/(?P<phone_number>\d+)/$', RemindersTester.as_view(), name='ils_reminders_tester'),
    url(r'save_ils_note', 'save_ils_note', name='save_ils_note'),
    url(r'fix_groups_in_location', 'fix_groups_in_location', name='fix_groups_in_location')
)

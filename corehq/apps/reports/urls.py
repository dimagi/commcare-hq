from django.conf.urls.defaults import *
from corehq.apps.domain.decorators import login_and_domain_required as protect
from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, CustomProjectReportDispatcher

dodoma_reports = patterns('corehq.apps.reports.dodoma',
    url('^household_verification_json$', 'household_verification_json'),
    url('^household_verification/$', 'household_verification'),
)

_phonelog_context = {
    'report': {
        'name': "Device Logs",
    }
}

custom_report_urls = patterns('',
    CustomProjectReportDispatcher.url_pattern(),
)

phonelog_reports = patterns('',
    url(r'^$', 'phonelog.views.devices', name="phonelog_devices", kwargs={
        'template': 'reports/phonelog/devicelist.html',
        'context': _phonelog_context
    }),
    url(r'^(?P<device>[\w\-]+)/$', 'phonelog.views.device_log', name="device_log", kwargs={
        'template': 'reports/phonelog/devicelogs.html',
        'context': _phonelog_context
    }),
    url(r'^(?P<device>[\w\-]+)/raw/$', 'phonelog.views.device_log_raw', name="device_log_raw", kwargs={
        'template': 'reports/phonelog/devicelogs_raw.html',
        'context': _phonelog_context
    }),
)

urlpatterns = patterns('corehq.apps.reports.views',
    url(r'^$', "default", name="reports_home"),

    url(r'^case_data/(?P<case_id>[\w\-]+)/$', 'case_details', name="case_details"),

    # Download and view form data
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/$', 'form_data', name='render_form_data'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download/$', 'download_form', name='download_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download/(?P<attachment>[\w.-_]+)?$',
        'download_attachment', name='download_attachment'),

    # Custom Hook for Dodoma TODO should this be here?
    url(r'^dodoma/', include(dodoma_reports)),


    # Create and Manage Custom Exports
    url(r"^export/$", 'export_data'),
    url(r"^export/customize/$", 'custom_export', name="custom_export"),
    url(r"^export/custom/(?P<export_id>[\w\-]+)/edit/$", 'edit_custom_export', name="edit_custom_export"),
    url(r"^export/custom/(?P<export_id>[\w\-]+)/delete/$", 'delete_custom_export', name="delete_custom_export"),

    # Download Exports
    ## Custom
    url(r"^export/custom/(?P<export_id>[\w\-]+)/download/$", 'export_default_or_custom_data', name="export_custom_data"),
    ## Default
    url(r"^export/default/download/$", "export_default_or_custom_data", name="export_default_data"),
    ## Bulk
    url(r"^export/bulk/download/$", "export_default_or_custom_data", name="export_bulk_download", kwargs=dict(bulk_export=True)),
    ## saved
    url(r"^export/saved/download/(?P<export_id>[\w\-]+)/$", "hq_download_saved_export", name="hq_download_saved_export"),

    # Saved reports
    url(r"^configs$", 'add_config', name='add_report_config'),
    url(r"^configs/(?P<config_id>[\w-]+)$", 'delete_config',
        name='delete_report_config'),

    # Scheduled reports
    url(r'^scheduled_reports/(?P<scheduled_report_id>[\w-]+)?$',
        'edit_scheduled_report', name="edit_scheduled_report"),
    url(r'^scheduled_report/(?P<scheduled_report_id>[\w-]+)/delete$',
        'delete_scheduled_report', name='delete_scheduled_report'),
    url(r'^send_test_scheduled_report/(?P<scheduled_report_id>[\w-]+)/$',
         'send_test_scheduled_report', name='send_test_scheduled_report'),
    url(r'^view_scheduled_report/(?P<scheduled_report_id>[\w_]+)/$',
        'view_scheduled_report', name='view_scheduled_report'),

    # Internal Use
    url(r"^export/forms/all/$", 'export_all_form_metadata', name="export_all_form_metadata"),
    url(r'^download/cases/$', 'download_cases', name='download_cases'),

    # TODO should this even be here?
    url(r'^phonelog/', include(phonelog_reports)),

    url(r'^custom/', include(custom_report_urls)),
    ProjectReportDispatcher.url_pattern(),
)

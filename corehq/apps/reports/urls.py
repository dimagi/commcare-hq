from django.conf.urls.defaults import *
from corehq.apps.domain.decorators import login_and_domain_required as protect

dodoma_reports = patterns('corehq.apps.reports.dodoma',
    url('^household_verification_json$', 'household_verification_json'),
    url('^household_verification/$', 'household_verification'),
)

_phonelog_context = {
    'report': {
        'name': "Device Logs",
    }
}

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
    url(r'^$', "default", name="default_report"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/$', 'case_details', name="case_details"),

    url(r'^form_data/(?P<instance_id>[\w\-]+)/$', 'form_data', name='render_form_data'),
    url(r'^form_data/(?P<instance_id>[\w\-]+)/download/$', 'download_form', name='download_form'),
    url(r'^form_data/(?P<instance_id>[\w\-]+)/download/(?P<attachment>[\w.-_]+)?$',
        'download_attachment', name='download_attachment'),

    url(r'^dodoma/', include(dodoma_reports)),

    # useful for debugging email reports
    url(r'^emaillist/$', 'emaillist', name="emailable_report_list"),
    url(r'^emailtest/(?P<report_slug>[\w_]+)/$', 'emailtest', name="emailable_report_test"),

    # export data
    url(r"^export/$", 'export_data'),
    url(r"^export_async/$", 'export_data_async'),
    # url(r'^excel_export_data/$', 'excel_export_data', name="excel_export_data_report"),
    
    url(r"^export/customize/$", 'custom_export', name="custom_export"),
    url(r"^export/custom/(?P<export_id>[\w\-]+)/edit/$", 'edit_custom_export', name="edit_custom_export"),
    url(r"^export/custom/(?P<export_id>[\w\-]+)/delete/$", 'delete_custom_export', name="delete_custom_export"),
    url(r"^export/custom/(?P<export_id>[\w\-]+)/download/$", 'export_custom_data', name="export_custom_data"),
    url(r"^export/forms/all/$", 'export_all_form_metadata', name="export_all_form_metadata"),
    
    # url(r'^case_export/$', 'case_export', name='case_export'),
    url(r'^download/cases/$', 'download_cases', name='download_cases'),

    url(r'^phonelog/', include(phonelog_reports)),

    # HQReport handlers
    url(r'^json/(?P<report_slug>[\w_]+)/$', 'report_dispatcher', name="json_report_dispatcher", kwargs={
        'return_json': True
    }),
    # HQReport handlers
    url(r'^export/(?P<report_slug>[\w_]+)/$', 'custom_report_dispatcher', name="export_report_dispatcher", kwargs={
        'export': True
    }),
    url(r'^custom/(?P<report_slug>[\w_]+)/$', 'custom_report_dispatcher', name="custom_report_dispatcher"),
    url(r'^(?P<report_slug>[\w_]+)/$', 'report_dispatcher', name="report_dispatcher"),


)


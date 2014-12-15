import logging

from django.conf.urls.defaults import *
from django.core.exceptions import ImproperlyConfigured
from corehq.apps.reports.util import get_installed_custom_modules
from corehq.apps.reports.dispatcher import (ProjectReportDispatcher, 
        CustomProjectReportDispatcher, BasicReportDispatcher)

# from .filters.urls import urlpatterns as filter_urls
from corehq.apps.example_reports.testreport import TestReport
from corehq.apps.userreports.reports.view import ConfigurableReport
from .filters import urls as filter_urls


custom_report_urls = patterns('',
    CustomProjectReportDispatcher.url_pattern(),
)

urlpatterns = patterns('corehq.apps.reports.views',
    TestReport.url_pattern(),
    ConfigurableReport.url_pattern(),
    url(r'^$', "default", name="reports_home"),
    url(r'^saved/', "saved_reports", name="saved_reports"),
    url(r'^saved_reports', 'old_saved_reports'),

    url(r'^case_data/(?P<case_id>[\w\-]+)/$', 'case_details', name="case_details"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/view/xml/$', 'case_xml', name="single_case_xml"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/rebuild/$', 'rebuild_case_view', name="rebuild_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/close/$', 'close_case_view', name="close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/undo-close/$', 'undo_close_case_view', name="undo_close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/export_transactions/$',
        'export_case_transactions', name="export_case_transactions"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/(?P<xform_id>[\w\-:]+)/$', 'case_form_data', name="case_form_data"),

    # Download and view form data
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/$', 'form_data', name='render_form_data'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download/$', 'download_form', name='download_form'),
    url(r'^form_data/download/media/$',
        'form_multimedia_export', name='form_multimedia_export'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download-attachment/$',
        'download_attachment', name='download_attachment'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/archive/$', 'archive_form', name='archive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/unarchive/$', 'unarchive_form', name='unarchive_form'),

    # export API
    url(r"^export/$", 'export_data'),

    # Download Exports
    # todo should eventually be moved to corehq.apps.export
    # Custom
    url(r"^export/custom/(?P<export_id>[\w\-]+)/download/$", 'export_default_or_custom_data', name="export_custom_data"),
    # Default
    url(r"^export/default/download/$", "export_default_or_custom_data", name="export_default_data"),
    # Bulk
    url(r"^export/bulk/download/$", "export_default_or_custom_data", name="export_bulk_download", kwargs=dict(bulk_export=True)),
    # saved
    url(r"^export/saved/download/(?P<export_id>[\w\-]+)/$", "hq_download_saved_export", name="hq_download_saved_export"),
    url(r"^export/saved/update/$", "hq_update_saved_export", name="hq_update_saved_export"),

    # Full Excel export
    url(r'^full_excel_export/(?P<export_hash>[\w\-]+)/(?P<format>[\w\-]+)$', "export_report", name="export_report"),

    # once off email
    url(r"^email_onceoff/(?P<report_slug>[\w_]+)/$", 'email_report'),
    url(r"^custom/email_onceoff/(?P<report_slug>[\w_]+)/$", 'email_report',
        kwargs=dict(report_type=CustomProjectReportDispatcher.prefix)),

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
    url(r"^export/forms/all/async/$", 'export_all_form_metadata_async', name="export_all_form_metadata_async"),
    url(r'^download/cases/$', 'download_cases', name='download_cases'),

    url(r'^custom/', include(custom_report_urls)),
    url(r'^filters/', include(filter_urls)),
    ProjectReportDispatcher.url_pattern(),
)

report_urls = patterns('',
    BasicReportDispatcher.url_pattern(),
)

for module in get_installed_custom_modules():
    module_name = module.__name__.split('.')[-1]
    try:
        custom_report_urls += patterns('',
             (r"^%s/" % module_name, include('{0}.urls'.format(module.__name__))),
        )
    except ImproperlyConfigured:
        logging.info("Module %s does not provide urls" % module_name)

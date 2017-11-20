from __future__ import absolute_import
import logging

from django.conf.urls import include, url
from django.core.exceptions import ImproperlyConfigured

from corehq.apps.reports.standard.forms.reports import ReprocessXFormErrorView
from corehq.apps.userreports.reports.view import (
    ConfigurableReport,
    CustomConfigurableReportDispatcher,
)
from corehq.apps.userreports.views import (
    ConfigureReport,
    EditReportInBuilder,
    ReportBuilderDataSourceSelect,
    ReportBuilderPaywallPricing,
    ReportBuilderPaywallActivatingSubscription,
    ReportPreview,
)

from .dispatcher import (
    BasicReportDispatcher,
    CustomProjectReportDispatcher,
    ProjectReportDispatcher,
)
from .filters import urls as filter_urls
from .util import get_installed_custom_modules
from .views import (
    EditFormInstance,
    AddSavedReportConfigView,
    FormDataView,
    CaseDetailsView,
    CaseAttachmentsView,
    MySavedReportsView,
    ScheduledReportsView,
    default,
    old_saved_reports,
    case_forms,
    case_xml,
    rebuild_case_view,
    resave_case,
    close_case_view,
    undo_close_case_view,
    export_case_transactions,
    case_form_data,
    download_form,
    restore_edit,
    form_multimedia_export,
    archive_form,
    resave_form,
    unarchive_form,
    project_health_user_details,
    export_data,
    export_default_or_custom_data,
    hq_download_saved_export,
    hq_deid_download_saved_export,
    hq_update_saved_export,
    export_report,
    email_report,
    delete_config,
    delete_scheduled_report,
    send_test_scheduled_report,
    view_scheduled_report,
    export_all_form_metadata,
    export_all_form_metadata_async,
    download_cases,
    download_cases_internal,
)


custom_report_urls = [
    CustomProjectReportDispatcher.url_pattern(),
]

urlpatterns = [
    ConfigurableReport.url_pattern(),
    CustomConfigurableReportDispatcher.url_pattern(),

    # Report Builder
    url(r'^builder/select_source/$', ReportBuilderDataSourceSelect.as_view(),
        name=ReportBuilderDataSourceSelect.urlname),
    url(r'^builder/configure/$', ConfigureReport.as_view(), name=ConfigureReport.urlname),
    url(r'^builder/preview/(?P<data_source>[\w\-]+)/$', ReportPreview.as_view(), name=ReportPreview.urlname),
    url(r'^builder/edit/(?P<report_id>[\w\-]+)/$', EditReportInBuilder.as_view(), name='edit_report_in_builder'),
    url(r'builder/subscribe/pricing/$', ReportBuilderPaywallPricing.as_view(),
        name=ReportBuilderPaywallPricing.urlname),
    url(r'builder/subscribe/activating_subscription/$', ReportBuilderPaywallActivatingSubscription.as_view(),
        name=ReportBuilderPaywallActivatingSubscription.urlname),

    url(r'^$', default, name="reports_home"),
    url(r'^saved/', MySavedReportsView.as_view(), name=MySavedReportsView.urlname),
    url(r'^saved_reports', old_saved_reports, name='old_saved_reports'),

    url(r'^case_data/(?P<case_id>[\w\-]+)/$', CaseDetailsView.as_view(), name=CaseDetailsView.urlname),
    url(r'^case_data/(?P<case_id>[\w\-]+)/forms/$', case_forms, name="single_case_forms"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/attachments/$',
        CaseAttachmentsView.as_view(), name=CaseAttachmentsView.urlname),
    url(r'^case_data/(?P<case_id>[\w\-]+)/view/xml/$', case_xml, name="single_case_xml"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/rebuild/$', rebuild_case_view, name="rebuild_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/resave/$', resave_case, name="resave_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/close/$', close_case_view, name="close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/undo-close/$', undo_close_case_view, name="undo_close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/export_transactions/$',
        export_case_transactions, name="export_case_transactions"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/(?P<xform_id>[\w\-:]+)/$', case_form_data, name="case_form_data"),

    # Download and view form data
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/$', FormDataView.as_view(), name=FormDataView.urlname),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download/$', download_form, name='download_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/edit/$', EditFormInstance.as_view(), name='edit_form_instance'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/restore_version/$', restore_edit, name='restore_edit'),
    url(r'^form_data/download/media/$',
        form_multimedia_export, name='form_multimedia_export'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/archive/$', archive_form, name='archive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/unarchive/$', unarchive_form, name='unarchive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/rebuild/$', resave_form, name='resave_form'),

    # project health ajax
    url(r'^project_health/ajax/(?P<user_id>[\w\-]+)/$', project_health_user_details,
        name='project_health_user_details'),

    # export API
    url(r"^export/$", export_data, name='export_data'),

    # Download Exports
    # todo should eventually be moved to corehq.apps.export
    # Custom
    url(r"^export/custom/(?P<export_id>[\w\-]+)/download/$", export_default_or_custom_data,
        name="export_custom_data"),
    # Default
    url(r"^export/default/download/$", export_default_or_custom_data, name="export_default_data"),
    # Bulk
    url(r"^export/bulk/download/$", export_default_or_custom_data,
        name="export_bulk_download", kwargs=dict(bulk_export=True)),
    # saved
    url(r"^export/saved/download/(?P<export_id>[\w\-]+)/$", hq_download_saved_export,
        name="hq_download_saved_export"),
    url(r"^export/saved/download/deid/(?P<export_id>[\w\-]+)/$", hq_deid_download_saved_export,
        name="hq_deid_download_saved_export"),
    url(r"^export/saved/update/$", hq_update_saved_export, name="hq_update_saved_export"),

    # Full Excel export
    url(r'^full_excel_export/(?P<export_hash>[\w\-]+)/(?P<format>[\w\-]+)$', export_report, name="export_report"),

    # once off email
    url(r"^email_onceoff/(?P<report_slug>[\w_]+)/$", email_report, kwargs=dict(once=True), name='email_report'),
    url(r"^custom/email_onceoff/(?P<report_slug>[\w_]+)/$", email_report,
        kwargs=dict(report_type=CustomProjectReportDispatcher.prefix, once=True), name='email_onceoff'),

    # Saved reports
    url(r"^configs$", AddSavedReportConfigView.as_view(), name=AddSavedReportConfigView.name),
    url(r"^configs/(?P<config_id>[\w-]+)$", delete_config,
        name='delete_report_config'),

    # Scheduled reports
    url(r'^scheduled_reports/(?P<scheduled_report_id>[\w-]+)?$',
        ScheduledReportsView.as_view(), name=ScheduledReportsView.urlname),
    url(r'^scheduled_report/(?P<scheduled_report_id>[\w-]+)/delete$',
        delete_scheduled_report, name='delete_scheduled_report'),
    url(r'^send_test_scheduled_report/(?P<scheduled_report_id>[\w-]+)/$',
        send_test_scheduled_report, name='send_test_scheduled_report'),
    url(r'^view_scheduled_report/(?P<scheduled_report_id>[\w_]+)/$',
        view_scheduled_report, name='view_scheduled_report'),

    # Internal Use
    url(r"^export/forms/all/$", export_all_form_metadata, name="export_all_form_metadata"),
    url(r"^export/forms/all/async/$", export_all_form_metadata_async, name="export_all_form_metadata_async"),
    url(r'^download/cases/$', download_cases, name='download_cases'),
    url(r'^download/internal/cases/$', download_cases_internal, name='download_cases_internal'),
    url(r'^reprocess_error_form/$', ReprocessXFormErrorView.as_view(),
        name=ReprocessXFormErrorView.urlname),

    url(r'^custom/', include(custom_report_urls)),
    url(r'^filters/', include(filter_urls)),
    ProjectReportDispatcher.url_pattern(),
]

report_urls = [
    BasicReportDispatcher.url_pattern(),
]

for module in get_installed_custom_modules():
    module_name = module.__name__.split('.')[-1]
    try:
        custom_report_urls += [
             url(r"^%s/" % module_name, include('{0}.urls'.format(module.__name__))),
        ]
    except ImproperlyConfigured:
        logging.info("Module %s does not provide urls" % module_name)

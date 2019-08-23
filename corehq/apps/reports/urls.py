from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.conf.urls import include, url
from django.core.exceptions import ImproperlyConfigured

from corehq.apps.reports.standard.forms.reports import ReprocessXFormErrorView
from corehq.apps.userreports.reports.view import (
    ConfigurableReportView,
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
    CaseDataView,
    CaseAttachmentsView,
    MySavedReportsView,
    ScheduledReportsView,
    case_forms,
    case_property_changes,
    case_property_names,
    download_case_history,
    case_xml,
    edit_case_view,
    rebuild_case_view,
    resave_case_view,
    close_case_view,
    undo_close_case_view,
    export_case_transactions,
    case_form_data,
    download_form,
    restore_edit,
    archive_form,
    edit_form,
    resave_form_view,
    unarchive_form,
    project_health_user_details,
    export_report,
    email_report,
    delete_config,
    delete_scheduled_report,
    send_test_scheduled_report,
    view_scheduled_report,
)


custom_report_urls = [
    CustomProjectReportDispatcher.url_pattern(),
]

urlpatterns = [
    ConfigurableReportView.url_pattern(),
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

    url(r'^$', MySavedReportsView.as_view(), name="reports_home"),
    url(r'^saved/', MySavedReportsView.as_view(), name=MySavedReportsView.urlname),
    url(r'^saved_reports', MySavedReportsView.as_view(), name="old_saved_reports"),

    url(r'^case_data/(?P<case_id>[\w\-]+)/$', CaseDataView.as_view(), name=CaseDataView.urlname),
    url(r'^case_data/(?P<case_id>[\w\-]+)/forms/$', case_forms, name="single_case_forms"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/attachments/$',
        CaseAttachmentsView.as_view(), name=CaseAttachmentsView.urlname),
    url(r'^case_data/(?P<case_id>[\w\-]+)/view/xml/$', case_xml, name="single_case_xml"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/properties/$', case_property_names, name="case_property_names"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/history/$', download_case_history, name="download_case_history"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/edit/$', edit_case_view, name="edit_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/rebuild/$', rebuild_case_view, name="rebuild_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/resave/$', resave_case_view, name="resave_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/close/$', close_case_view, name="close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/undo-close/(?P<xform_id>[\w\-:]+)/$',
        undo_close_case_view, name="undo_close_case"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/export_transactions/$',
        export_case_transactions, name="export_case_transactions"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/(?P<xform_id>[\w\-:]+)/$', case_form_data, name="case_form_data"),
    url(r'^case_data/(?P<case_id>[\w\-]+)/case_property/(?P<case_property_name>[\w_\-.]+)/$',
        case_property_changes, name="case_property_changes"),

    # Download and view form data
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/$', FormDataView.as_view(), name=FormDataView.urlname),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/download/$', download_form, name='download_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/edit/$', EditFormInstance.as_view(), name='edit_form_instance'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/restore_version/$', restore_edit, name='restore_edit'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/correct_data/$', edit_form, name='edit_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/archive/$', archive_form, name='archive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/unarchive/$', unarchive_form, name='unarchive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/rebuild/$', resave_form_view, name='resave_form'),

    # project health ajax
    url(r'^project_health/ajax/(?P<user_id>[\w\-]+)/$', project_health_user_details,
        name='project_health_user_details'),

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

    # V2 Reports
    url(r'^v2/', include('corehq.apps.reports.v2.urls')),

    # Internal Use
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

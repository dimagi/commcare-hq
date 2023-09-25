from django.conf.urls import include, re_path as url

from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.reports.standard.forms.reports import ReprocessXFormErrorView
from corehq.apps.reports.standard.cases.case_data import (
    CaseAttachmentsView,
    CaseDataView,
    case_forms,
    case_property_changes,
    case_property_names,
    case_xml,
    close_case_view,
    download_case_history,
    edit_case_view,
    export_case_transactions,
    rebuild_case_view,
    resave_case_view,
    undo_close_case_view,
)
from corehq.apps.reports.standard.tableau import TableauView, tableau_visualization_ajax
from corehq.apps.userreports.reports.view import (
    ConfigurableReportView,
    CustomConfigurableReportDispatcher,
)
from corehq.apps.userreports.views import (
    ConfigureReport,
    EditReportInBuilder,
    ReportBuilderDataSourceSelect,
    ReportBuilderPaywallActivatingSubscription,
    ReportBuilderPaywallPricing,
    ReportPreview,
)

from .dispatcher import (
    CustomProjectReportDispatcher,
    ProjectReportDispatcher,
    ReleaseManagementReportDispatcher,
    UserManagementReportDispatcher,
)
from .filters import urls as filter_urls
from .views import (
    AddSavedReportConfigView,
    FormDataView,
    MySavedReportsView,
    ScheduledReportsView,
    archive_form,
    case_form_data,
    delete_config,
    soft_delete_form,
    delete_scheduled_report,
    download_form,
    edit_form,
    email_report,
    export_report,
    get_or_create_filter_hash,
    project_health_user_details,
    reports_home,
    resave_form_view,
    restore_edit,
    send_test_scheduled_report,
    unarchive_form,
    view_form_attachment,
    view_scheduled_report,
    copy_cases,
)

custom_report_urls = [
    CustomProjectReportDispatcher.url_pattern(),
]

user_management_urls = [
    UserManagementReportDispatcher.url_pattern(),
]

release_management_urls = [
    ReleaseManagementReportDispatcher.url_pattern()
]

urlpatterns = [
    ConfigurableReportView.url_pattern(),
    CustomConfigurableReportDispatcher.url_pattern(),
    url(r'^copy_cases/$', copy_cases, name='copy_cases'),

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

    url(r'^$', reports_home, name="reports_home"),
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
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/restore_version/$', restore_edit, name='restore_edit'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/correct_data/$', edit_form, name='edit_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/archive/$', archive_form, name='archive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/unarchive/$', unarchive_form, name='unarchive_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/delete/$', soft_delete_form, name='soft_delete_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/rebuild/$', resave_form_view, name='resave_form'),
    url(r'^form_data/(?P<instance_id>[\w\-:]+)/attachment/(?P<attachment_id>.*)$', view_form_attachment),

    # project health ajax
    url(r'^project_health/ajax/(?P<user_id>[\w\-]+)/$', project_health_user_details,
        name='project_health_user_details'),

    # Full Excel export
    url(r'^full_excel_export/(?P<export_hash>[\w\-]+)/(?P<format>[\w\-]+)$', export_report, name="export_report"),

    # once off email
    url(r"^email_onceoff/(?P<report_slug>[\w_]+)/$", email_report, kwargs=dict(once=True), name='email_report'),
    url(r"^custom/email_onceoff/(?P<report_slug>[\w_]+)/$", email_report,
        kwargs=dict(dispatcher_class=CustomProjectReportDispatcher, once=True), name='email_onceoff'),

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

    url(r'^tableau/(?P<viz_id>[\d]+)/$', TableauView.as_view(), name=TableauView.urlname),
    url(r'^tableau/visualization/$', tableau_visualization_ajax, name='tableau_visualization_ajax'),

    # Internal Use
    url(r'^reprocess_error_form/$', ReprocessXFormErrorView.as_view(),
        name=ReprocessXFormErrorView.urlname),

    url(r'^custom/', include(custom_report_urls)),
    url(r'^filters/', include(filter_urls)),
    ProjectReportDispatcher.url_pattern(),
    url(r'^user_management/', include(user_management_urls)),
    url(r'^release_management/', include(release_management_urls)),
    url(r'^get_or_create_hash/', get_or_create_filter_hash, name='get_or_create_filter_hash'),
]

# Exporting Case List Explorer reports with the word " on*" at the end of the search query
# get filtered by the WAF
waf_allow("XSS_BODY", hard_code_pattern=r'^/a/([\w\.:-]+)/reports/export/(case_list_explorer|duplicate_cases)/$')

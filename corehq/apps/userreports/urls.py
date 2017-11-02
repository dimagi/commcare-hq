from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.userreports.reports.view import DownloadUCRStatusView, ucr_download_job_poll
from corehq.apps.userreports.views import (
    UserConfigReportsHomeView,
    EditConfigReportView,
    CreateConfigReportView,
    ImportConfigReportView,
    CreateDataSourceView,
    EditDataSourceView,
    PreviewDataSourceView,
    CreateDataSourceFromAppView,
    report_source_json,
    delete_report,
    data_source_json,
    delete_data_source,
    rebuild_data_source,
    resume_building_data_source,
    build_data_source_in_place,
    recalculate_data_source,
    export_data_source,
    data_source_status,
    choice_list_api,
    ExpressionDebuggerView,
    evaluate_expression,
    undelete_data_source, undelete_report, DataSourceDebuggerView, evaluate_data_source)

urlpatterns = [
    url(r'^$', UserConfigReportsHomeView.as_view(),
        name=UserConfigReportsHomeView.urlname),
    url(r'^reports/create/$', CreateConfigReportView.as_view(),
        name=CreateConfigReportView.urlname),
    url(r'^reports/import/$', ImportConfigReportView.as_view(),
        name=ImportConfigReportView.urlname),
    url(r'^reports/edit/(?P<report_id>[\w-]+)/$', EditConfigReportView.as_view(),
        name=EditConfigReportView.urlname),
    url(r'^reports/source/(?P<report_id>[\w-]+)/$', report_source_json, name='configurable_report_json'),
    url(r'^reports/delete/(?P<report_id>[\w-]+)/$', delete_report, name='delete_configurable_report'),
    url(r'^reports/undelete/(?P<report_id>[\w-]+)/$', undelete_report, name='undo_delete_configurable_report'),
    url(r'^data_sources/create/$', CreateDataSourceView.as_view(),
        name=CreateDataSourceView.urlname),
    url(r'^data_sources/create_from_app/$', CreateDataSourceFromAppView.as_view(),
        name=CreateDataSourceFromAppView.urlname),
    url(r'^data_sources/edit/(?P<config_id>[\w-]+)/$', EditDataSourceView.as_view(),
        name=EditDataSourceView.urlname),
    url(r'^data_sources/source/(?P<config_id>[\w-]+)/$', data_source_json, name='configurable_data_source_json'),
    url(r'^data_sources/delete/(?P<config_id>[\w-]+)/$', delete_data_source,
        name='delete_configurable_data_source'),
    url(r'^data_sources/undelete/(?P<config_id>[\w-]+)/$', undelete_data_source,
        name='undo_delete_data_source'),
    url(r'^data_sources/rebuild/(?P<config_id>[\w-]+)/$', rebuild_data_source,
        name='rebuild_configurable_data_source'),
    url(r'^data_sources/resume/(?P<config_id>[\w-]+)/$', resume_building_data_source,
        name='resume_build'),
    url(r'^data_sources/build_in_place/(?P<config_id>[\w-]+)/$', build_data_source_in_place,
        name='build_in_place'),
    url(r'^data_sources/recalculate/(?P<config_id>[\w-]+)/$', recalculate_data_source,
        name='recalculate_data_source'),
    url(r'^data_sources/preview/(?P<config_id>[\w-]+)/$',
        PreviewDataSourceView.as_view(),
        name=PreviewDataSourceView.urlname),
    url(r'^data_sources/export/(?P<config_id>[\w-]+)/$', export_data_source,
        name='export_configurable_data_source'),
    url(r'^data_sources/status/(?P<config_id>[\w-]+)/$', data_source_status,
        name='configurable_data_source_status'),
    url(r'^expression_debugger/$', ExpressionDebuggerView.as_view(),
        name='expression_debugger'),
    url(r'^data_source_debugger/$', DataSourceDebuggerView.as_view(),
        name='data_source_debugger'),
    url(r'^export_status/(?P<download_id>[0-9a-fA-Z]{25,32})/(?P<subreport_slug>[\w-]+)/$',
        DownloadUCRStatusView.as_view(), name=DownloadUCRStatusView.urlname),
    url(r'^export_job_poll/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        ucr_download_job_poll, name='ucr_download_job_poll'),

    # apis
    url(r'^api/choice_list/(?P<report_id>[\w-]+)/(?P<filter_id>[\w-]+)/$',
        choice_list_api, name='choice_list_api'),
    url(r'^expression_evaluator/$', evaluate_expression, name='expression_evaluator'),
    url(r'^data_source_evaluator/$', evaluate_data_source, name='data_source_evaluator'),
]

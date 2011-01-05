from django.conf.urls.defaults import *

actual_reports = patterns('corehq.apps.reports.views',
    url('submit_history', 'submit_history', name="submit_history_report"),
    url('submit_time_punchcard', 'submit_time_punchcard', name="submit_time_punchcard"),
)

paging_reports = patterns('corehq.apps.reports.views',
    url('submit_history/(?P<individual>.*)/', 'paging_submit_history', name='paging_submit_history'),
)

urlpatterns = patterns('corehq.apps.reports.views',
    url(r'^$', "default", name="default_report"),

    url(r'^user_summary/$', 'user_summary', name='user_summary_report'),
    url(r'^individual_summary/', 'individual_summary', name="individual_summary_report"),
    url(
        r'^daily_submissions/$',
        'daily_submissions',
        kwargs=dict(view_name="reports/daily_submissions", title="Daily Submissions by user"),
        name='daily_submissions_report'
    ),
    url(
        r'^daily_completions/$',
        'daily_submissions',
        kwargs=dict(view_name="reports/daily_completions", title="Daily Completions by user"),
        name='daily_completions_report'
    ),


    url(r"^export/", 'export_data'),
    url(r'^excel_export_data/$', 'excel_export_data', name="excel_export_data_report"),
    url(r'^r/', include(actual_reports)),
    url(r'^paging/', include(paging_reports)),
)

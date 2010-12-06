from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.reports.views',
    url(r'^$', "report_list", name="report_list"),

    url(r'^user_summary/$', 'user_summary', name='user_summary_report'),
    url(
        r'^daily_submissions/$',
        'daily_submissions',
        kwargs=dict(view_name="reports/daily_submissions"),
        name='daily_submissions_report'
    ),
    url(
        r'^daily_completions/$',
        'daily_submissions',
        kwargs=dict(view_name="reports/daily_completions"),
        name='daily_completions_report'
    ),
)

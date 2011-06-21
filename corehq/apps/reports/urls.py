from django.conf.urls.defaults import *
from corehq.apps.domain.decorators import login_and_domain_required as protect
from corehq.apps.reports.views import SubmitHistory

actual_reports = patterns('corehq.apps.reports.views',
    url('submit_history', protect(SubmitHistory.view), name="submit_history_report"),
    url('submit_time_punchcard', 'submit_time_punchcard', name="submit_time_punchcard"),
    url('submit_trends', 'submit_trends', name="submit_trends"),
    url('submit_distribution', 'submit_distribution', name="submit_distribution"),
)

paging_reports = patterns('corehq.apps.reports.views',
    url('submit_history/(?P<individual>.*)/(?P<show_unregistered>.*)/', protect(SubmitHistory.ajax_view), name='paging_submit_history'),
    url('submit_history/(?P<individual>.*)/$', "paging_case_list", name='paging_case_list'),
)

dodoma_reports = patterns('corehq.apps.reports.dodoma',
    url('household_verification_json', 'household_verification_json'),
    url('household_verification', 'household_verification'),
)

urlpatterns = patterns('corehq.apps.reports.views',
    url(r'^$', "default", name="default_report"),

    url(r'^user_summary/$', 'user_summary', name='user_summary_report'),
    url(r'^submission_log/', 'submission_log', name="submission_log_report"),
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

    url('active_cases', 'active_cases', name="active_case_report"),
    url('case_activity', 'case_activity', name="case_activity_report"),
    url('case_list/$', 'case_list', name="case_list_report"),
    url('case_data/(?P<case_id>\w+)/$', 'case_details', name="case_details"),


    url(r'^form_data/(?P<instance_id>\w+)/$', 'form_data', name='render_form_data'),
    url(r'^form_data/(?P<instance_id>\w+)/download/$', 'download_form', name='download_form'),
    url(r'^form_data/(?P<instance_id>\w+)/download/(?P<attachment>[\w.-_]+)?$', 
        'download_attachment', name='download_attachment'),
    # url(r'^partial/form_data/(?P<instance_id>.*)/$', 'form_data', name='render_form_data'),
    url(r"^export/", 'export_data'),
    url(r'^excel_export_data/$', 'excel_export_data', name="excel_export_data_report"),
    url(r'^r/', include(actual_reports)),
    url(r'^paging/', include(paging_reports)),
    url(r'^dodoma/', include(dodoma_reports)),

    url(r'^submissions_by_form/', 'submissions_by_form', name="submissions_by_form_report"),
    
    # useful for debugging email reports
    url(r'^emaillist/', 'emaillist', name="emailable_report_list"),
    url(r'^emailtest/(?P<report_slug>[\w_]+)/', 'emailtest', name="emailable_report_test"),
    
)

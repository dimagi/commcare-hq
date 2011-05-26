from corehq.apps.reports.views import daily_submissions, submissions_by_form
from corehq.apps.reports.schedule import BasicReportSchedule, ReportSchedule,\
    DomainedReportSchedule
from corehq.apps.hqadmin.views import domain_list


DAILY_SUBMISSIONS_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_submissions",
                                               "Daily Submissions by user")
DAILY_COMPLETION_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_completions",
                                               "Daily Completions by user")

SUBMISSIONS_BY_FORM_REPORT = DomainedReportSchedule(submissions_by_form,
                                            title="Submissions by Form")

ADMIN_DOMAIN_REPORT = ReportSchedule(domain_list, 
                                     title="Domain Summary", auth=lambda user: user.is_superuser)

SCHEDULABLE_REPORTS = {"daily_submissions": DAILY_SUBMISSIONS_REPORT,
                       "daily_completions": DAILY_COMPLETION_REPORT,
                       "admin_domains": ADMIN_DOMAIN_REPORT,
                       "submissions_by_form": SUBMISSIONS_BY_FORM_REPORT,
                       }
from corehq.apps.reports.views import daily_submissions
from corehq.apps.reports.schedule import BasicReportSchedule, ReportSchedule
from corehq.apps.hqadmin.views import domain_list


DAILY_SUBMISSIONS_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_submissions",
                                               "Daily Submissions by user")
DAILY_COMPLETION_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_completions",
                                               "Daily Completions by user")

ADMIN_DOMAIN_REPORT = ReportSchedule(domain_list, 
                                     title="Domain Summary")

SCHEDULABLE_REPORTS = {"daily_submissions": DAILY_SUBMISSIONS_REPORT,
                       "daily_completions": DAILY_COMPLETION_REPORT,
# not until we have permissions                       "admin_domains": ADMIN_DOMAIN_REPORT,
                       }
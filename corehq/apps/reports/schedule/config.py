from corehq.apps.reports.views import daily_submissions
from corehq.apps.reports.schedule import BasicReportSchedule


DAILY_SUBMISSIONS_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_submissions",
                                               "Daily Submissions by user")
DAILY_COMPLETION_REPORT = BasicReportSchedule(daily_submissions, 
                                               "reports/daily_completions",
                                               "Daily Completions by user")

SCHEDULABLE_REPORTS = {"daily_submissions": DAILY_SUBMISSIONS_REPORT,
                       "daily_completions": DAILY_COMPLETION_REPORT
                       }
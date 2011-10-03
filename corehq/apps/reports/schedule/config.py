from corehq.apps.reports.views import daily_submissions, submissions_by_form, case_activity
from corehq.apps.reports.schedule import BasicReportSchedule, ReportSchedule,\
    DomainedReportSchedule
from corehq.apps.hqadmin.views import domain_list


SCHEDULABLE_REPORTS = ["daily_submissions",
                       "daily_completions",
                       "submissions_by_form",
                       "admin_domains",
                       "case_activity"]

class ScheduledReportFactory(object):
    """
    Factory access for scheduled reports
    """
    
    @classmethod
    def get_report(cls, slug):
        return getattr(cls, "_%s" % slug)()
        
    @classmethod
    def get_reports(cls):
        return dict((rep, cls.get_report(rep)) for rep in SCHEDULABLE_REPORTS)
    
    @classmethod
    def _daily_submissions(cls):
        return BasicReportSchedule(daily_submissions,
                                   "reports/daily_submissions",
                                   "Daily Submissions by user")
    
    @classmethod
    def _daily_completions(cls):
        return BasicReportSchedule(daily_submissions, 
                                   "reports/daily_completions",
                                   "Daily Completions by user")
        
    @classmethod
    def _submissions_by_form(cls):
        return DomainedReportSchedule(submissions_by_form,
                                      title="Submissions by Form")

    @classmethod
    def _case_activity(cls):
        return DomainedReportSchedule(case_activity,
                                      title="Case Activity")

    @classmethod
    def _admin_domains(cls):
        return ReportSchedule(domain_list, 
                              title="Domain Summary", auth=lambda user: user.is_superuser)
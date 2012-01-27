from corehq.apps.reports.schedule import BasicReportSchedule, ReportSchedule,\
    DomainedReportSchedule
from corehq.apps.hqadmin.views import domain_list
from corehq.apps.reports.standard import DailySubmissionsReport, DailyFormCompletionsReport, SubmissionsByFormReport, CaseActivityReport


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
        return BasicReportSchedule(DailySubmissionsReport)
    
    @classmethod
    def _daily_completions(cls):
        return BasicReportSchedule(DailyFormCompletionsReport)
        
    @classmethod
    def _submissions_by_form(cls):
        return BasicReportSchedule(SubmissionsByFormReport)

    @classmethod
    def _case_activity(cls):
        return BasicReportSchedule(CaseActivityReport)

    @classmethod
    def _admin_domains(cls):
        return ReportSchedule(domain_list,
                              title="Domain Summary", auth=lambda user: user.is_superuser)
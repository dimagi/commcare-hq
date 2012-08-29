from corehq.apps.reports.schedule import BasicReportSchedule, ReportSchedule, CustomReportSchedule
from corehq.apps.hqadmin.views import domain_list
from corehq.apps.reports._global.monitoring import CaseActivityReport, SubmissionsByFormReport, DailySubmissionsReport, DailyFormCompletionsReport
from django.conf import settings
from dimagi.utils.modules import to_function

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
        if slug.startswith("custom-"):
            custom_reports = {}
            for domain, values in settings.CUSTOM_REPORT_MAP.items():
                for heading, models in values.items():
                    for model in models:
                        klass = to_function(model)
                        custom_reports[klass.slug] = CustomReportSchedule(klass)
            return custom_reports[slug[len("custom-"):]]
        else:
            return getattr(cls, "_%s" % slug)()
        
    @classmethod
    def get_reports(cls, domain=None):
        reports = dict((rep, cls.get_report(rep)) for rep in SCHEDULABLE_REPORTS)
        if domain is not None:
            for heading, models in settings.CUSTOM_REPORT_MAP.get(domain, {}).items():
                for model in models:
                    klass = to_function(model)
                    slug = "custom-" + klass.slug
                    reports[slug] = CustomReportSchedule(klass)
        return reports
    
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
                              title="Domain Summary", auth=lambda request: request.user.is_superuser)

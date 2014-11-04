from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import ChildConsultationHistoryComplete, ChildConsultationHistory


class ChildConsultationHistoryReport(TDHReport):
    name = 'Child Consultation History'
    title = 'Child Consultation History'
    slug = 'child_consultation_history'
    base_template = "tdh/tdh_template.html"

    @property
    def data_provider(self):
        return ChildConsultationHistory(config=self.report_config)


class CompleteChildConsultationHistoryReport(ChildConsultationHistoryReport):
    @property
    def data_provider(self):
        return ChildConsultationHistoryComplete(config=self.report_config)

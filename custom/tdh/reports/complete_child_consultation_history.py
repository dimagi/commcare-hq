from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import ChildConsultationHistory


class CompleteChildConsultationHistoryReport(TDHReport):
    name = 'Complete Child Consultation History'
    slug = 'complete_child_consultation_history'

    @property
    def data_provider(self):
        return ChildConsultationHistory(config=self.report_config)

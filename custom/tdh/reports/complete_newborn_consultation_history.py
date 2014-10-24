from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import NewbornConsultationHistory


class CompleteNewBornConsultationHistoryReport(TDHReport):
    name = 'Complete Newborn Consultation History'
    slug = 'complete_newborn_consultation_history'

    @property
    def data_provider(self):
        return NewbornConsultationHistory(config=self.report_config)

from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import InfantConsultationHistory, InfantConsultationHistoryComplete


class InfantConsultationHistoryReport(TDHReport):
    name = 'Infant Consultation History'
    slug = 'infant_consultation_history'
    title = 'Infant Consultation History'
    base_template = "tdh/tdh_template.html"

    @property
    def data_provider(self):
        return InfantConsultationHistory(config=self.report_config)


class CompleteInfantConsultationHistoryReport(InfantConsultationHistoryReport):
    @property
    def data_provider(self):
        return InfantConsultationHistoryComplete(config=self.report_config)

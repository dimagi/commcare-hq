from django.utils.translation import ugettext_lazy
from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import InfantConsultationHistory, InfantConsultationHistoryComplete


class InfantConsultationHistoryReport(TDHReport):
    name = ugettext_lazy('Infant Consultation History')
    slug = 'infant_consultation_history'
    title = ugettext_lazy('Infant Consultation History')
    base_template = "tdh/tdh_template.html"

    @property
    def data_provider(self):
        return InfantConsultationHistory(config=self.report_config)


class CompleteInfantConsultationHistoryReport(InfantConsultationHistoryReport):
    @property
    def data_provider(self):
        return InfantConsultationHistoryComplete(config=self.report_config)

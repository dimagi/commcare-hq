from django.utils.translation import ugettext_lazy
from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import ChildConsultationHistoryComplete, ChildConsultationHistory


class ChildConsultationHistoryReport(TDHReport):
    name = ugettext_lazy('Child Consultation History')
    title = ugettext_lazy('Child Consultation History')
    slug = 'child_consultation_history'
    base_template = "tdh/tdh_template.html"

    @property
    def data_provider(self):
        return ChildConsultationHistory(config=self.report_config)


class CompleteChildConsultationHistoryReport(ChildConsultationHistoryReport):
    @property
    def data_provider(self):
        return ChildConsultationHistoryComplete(config=self.report_config)

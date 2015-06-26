from django.utils.translation import ugettext_noop
from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import NewbornConsultationHistory, NewbornConsultationHistoryComplete


class NewbornConsultationHistoryReport(TDHReport):
    name = ugettext_noop('Newborn Consultation History')
    slug = 'newborn_consultation_history'
    title = ugettext_noop('Newborn Consultation History')
    base_template = "tdh/tdh_template.html"

    @property
    def data_provider(self):
        return NewbornConsultationHistory(config=self.report_config)


class CompleteNewbornConsultationHistoryReport(NewbornConsultationHistoryReport):
    @property
    def data_provider(self):
        return NewbornConsultationHistoryComplete(config=self.report_config)

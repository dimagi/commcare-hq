from custom.tdh.reports import TDHReport


class CompleteNewBornConsultationHistoryReport(TDHReport):
    name = 'Complete Newborn Consultation History'
    slug = 'complete_newborn_consultation_history'

    @property
    def data_provider(self):
        return None

from custom.tdh.reports import TDHReport


class CompleteChildConsultationHistoryReport(TDHReport):
    name = 'Complete Child Consultation History'
    slug = 'complete_child_consultation_history'

    @property
    def data_provider(self):
        return None

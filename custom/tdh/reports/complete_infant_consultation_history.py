from custom.tdh.reports import TDHReport


class CompleteInfantConsultationHistoryReport(TDHReport):
    name = 'Complete Infant Consultation History'
    slug = 'complete_infant_consultation_history'

    @property
    def data_provider(self):
        return None

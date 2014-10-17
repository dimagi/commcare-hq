from custom.tdh.reports import TDHReport


class InfantConsultationHistoryReport(TDHReport):
    name = 'Infant Consultation History'
    slug = 'infant_consultation_history'

    @property
    def data_provider(self):
        return None

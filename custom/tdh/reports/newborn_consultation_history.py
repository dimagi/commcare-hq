from custom.tdh.reports import TDHReport


class NewbornConsultationHistory(TDHReport):
    name = 'Newborn Consultation History'
    slug = 'newborn_consultation_history'

    @property
    def data_provider(self):
        return None

from custom.tdh.reports import TDHReport


class ChildConsultationHistory(TDHReport):
    name = 'Child Consultation History'
    slug = 'child_consultation_history'

    @property
    def data_provider(self):
        return None

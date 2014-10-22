from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.tdh.reports import TDHReport
from custom.tdh.sqldata import InfantConsultationHistory


class CompleteInfantConsultationHistoryReport(TDHReport):
    name = 'Complete Infant Consultation History'
    title = 'Complete Infant Consultation History'
    slug = 'complete_infant_consultation_history'
    default_rows = 10

    @property
    def data_provider(self):
        return InfantConsultationHistory(config=self.report_config)
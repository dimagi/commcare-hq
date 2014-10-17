from custom.tdh.reports.child_consultation_history import ChildConsultationHistory
from custom.tdh.reports.complete_child_consultation_history import CompleteChildConsultationHistoryReport
from custom.tdh.reports.complete_infant_consultation_history import CompleteInfantConsultationHistoryReport
from custom.tdh.reports.complete_newborn_consultation_history import CompleteNewBornConsultationHistoryReport
from custom.tdh.reports.infant_consultation_history import InfantConsultationHistoryReport
from custom.tdh.reports.newborn_consultation_history import NewbornConsultationHistory

TDH_DOMAINS =  ('tdhtesting', )

CUSTOM_REPORTS = (
    ('Custom Reports', (
        CompleteInfantConsultationHistoryReport,
        CompleteNewBornConsultationHistoryReport,
        CompleteChildConsultationHistoryReport,
        InfantConsultationHistoryReport,
        NewbornConsultationHistory,
        ChildConsultationHistory
    )),
)
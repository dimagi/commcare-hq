from custom.enikshay.reports.case_finding import CaseFindingReport
from custom.enikshay.reports.treatment_outcome import TreatmentOutcomeReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        CaseFindingReport,
        TreatmentOutcomeReport
    )),
)

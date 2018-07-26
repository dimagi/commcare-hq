from __future__ import absolute_import
from __future__ import unicode_literals
from custom.enikshay.reports.adherence import AdherenceReport
from custom.enikshay.reports.case_finding import CaseFindingReport
from custom.enikshay.reports.historical_adherence import HistoricalAdherenceReport
from custom.enikshay.reports.treatment_outcome import TreatmentOutcomeReport
from custom.enikshay.reports.repeaters import ENikshayForwarderReport, ENikshayVoucherReport
from custom.enikshay.reports.worker_activity import EnikshayWorkerActivityReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        CaseFindingReport,
        TreatmentOutcomeReport,
        AdherenceReport,
        HistoricalAdherenceReport,
        ENikshayForwarderReport,
        EnikshayWorkerActivityReport,
        ENikshayVoucherReport,
    )),
)

from . import reports
from custom.opm.opm_reports.met_report import MetReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        reports.BeneficiaryPaymentReport,
        reports.IncentivePaymentReport,
        reports.HealthStatusReport,
        MetReport
    )),

)

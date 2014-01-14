from . import reports

CUSTOM_REPORTS = (
    ('Custom Reports', (
        reports.BeneficiaryPaymentReport,
        reports.IncentivePaymentReport,
        reports.HealthStatusReport,
    )),

)

from . import reports

CUSTOM_REPORTS = (
    ('Custom Reports', (
        reports.BeneficiaryPaymentReport,
        reports.IncentivePaymentReport,
        reports.NewHealthStatusReport,
        reports.MetReport,
        reports.HealthMapReport,
        reports.LongitudinalCMRReport,
    )),
)

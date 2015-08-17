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

hierarchy_config = {
    'lvl_1': {
        'prop': 'block',
        'name': 'Block'
    },
    'lvl_2': {
        'prop': 'gp',
        'name': 'Gram Panchayat'
    },
    'lvl_3': {
        'prop': 'awc',
        'name': 'AWC'
    }
}

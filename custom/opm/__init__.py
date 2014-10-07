from . import reports


CUSTOM_REPORTS = (
    ('Custom Reports', (
        reports.BeneficiaryPaymentReport,
        reports.IncentivePaymentReport,
        reports.HealthStatusReport,
        reports.MetReport,
        reports.HealthMapReport,
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
from django.utils.translation import ugettext_noop as _
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        ASHAFacilitatorsReport,
    )),
)

hierarchy_config = {
    'lvl_1': {
        'prop': 'district',
        'name': 'District'
    },
    'lvl_2': {
        'prop': 'block',
        'name': 'Block'
    },
    'lvl_3': {
        'prop': 'af',
        'name': 'AF'
    }
}

from django.utils.translation import ugettext_noop as _
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        ASHAFacilitatorsReport,
    )),
)

ASHA_FUNCTIONALITY_CHECKLIST_XMLNS = 'http://openrosa.org/formdesigner/8364a6d4357501413a1d9a8996d33245220a3505'

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

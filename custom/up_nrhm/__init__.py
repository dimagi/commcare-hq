from django.utils.translation import ugettext_noop as _
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport
from custom.up_nrhm.reports.asha_functionality_checklist_report import ASHAFunctionalityChecklistReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        ASHAFacilitatorsReport,
        ASHAFunctionalityChecklistReport,
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

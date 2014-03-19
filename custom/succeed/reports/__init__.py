from django.utils.translation import ugettext as _

PM1 = 'http://openrosa.org/formdesigner/111B09EB-DFFA-4613-9A16-A19BA6ED7D04'
PM2 = 'http://openrosa.org/formdesigner/4B52ADB2-AA79-4056-A13E-BB34871876A1'
PM3 = 'http://openrosa.org/formdesigner/5250590B-2EB2-46A8-9943-B7008CDA2BB9'
PM4 = 'http://openrosa.org/formdesigner/876cec8f07c0e29b9f9e2bd0b33c5c85bf0192ee'
CM1 = 'http://openrosa.org/formdesigner/9946952C-A2EB-43D5-A500-B386C56A49A7'
CM2 = 'http://openrosa.org/formdesigner/BCFFFE7E-8C93-4B4E-9589-FF12C710C255'
CM3 = 'http://openrosa.org/formdesigner/4EA3D459-7FB6-414F-B106-05E6E707568B'
CM4 = 'http://openrosa.org/formdesigner/263cc99e9f0cdbc55d307359c7b45a1e555f35d1'
CM5 = 'http://openrosa.org/formdesigner/8abd54794d8c5d592100b8cdf1f642903b7f4abe'
CM6 = 'http://openrosa.org/formdesigner/9b47556945c6476438c2ac2f0583e2ca0055e46a'
CM7 = 'http://openrosa.org/formdesigner/4b924f784e8dd6a23045649730e82f6a2e7ce7cf'
HUD1 = 'http://openrosa.org/formdesigner/24433229c5f25d0bd3ceee9bf70c72093056d1af'
HUD2 = 'http://openrosa.org/formdesigner/63f8287ac6e7dce0292ebac9b232b0d3bde327dc'
PD1 = 'http://openrosa.org/formdesigner/9eb0eaf6954791425d6d5f0b66db9a484cacd264'
PD2 = 'http://openrosa.org/formdesigner/69751bf3078369491e1c2f1e3c874895f762a4c1'
CHW1 = 'http://openrosa.org/formdesigner/4b368b1d73862abeca3bce67b6e09724b8dca850'
CHW2 = 'http://openrosa.org/formdesigner/cbc4e37437945bfda04e391d11006b6d02c24fc2'
CHW3 = 'http://openrosa.org/formdesigner/5d77815bf7631a527d8647cdbaa5971e367f6548'
CHW4 = 'http://openrosa.org/formdesigner/f8a741808584d772c4b899ef84db197da5b4d12a'
CUSTOM_EDIT = 'http://commcarehq.org/cloudcare/custom-edit'

EMPTY_FIELD = "---"

OUTPUT_DATE_FORMAT = "%m/%d/%Y"
INPUT_DATE_FORMAT = "%Y-%m-%d"

CM_MODULE = 0
HUD_MODULE = 1
PD_MODULE = 2
CHW_MODULE = 3

VISIT_SCHEDULE = [
    {
        'visit_name': _('CM Initial contact form'),
        'xmlns': CM1,
        'days': 5,
        'module_idx': CM_MODULE,
        'show_button': True,
        'target_date_case_property': 'CM1_form_target'
    },
    {
        'visit_name': _('CM Medical Record Review'),
        'xmlns': CM2,
        'days': 7,
        'module_idx': CM_MODULE,
        'show_button': True,
        'target_date_case_property': 'CM2_form_target'
    },
    {
        'visit_name': _('CM 1-week Telephone Call'),
        'xmlns': CM3,
        'days': 10,
        'module_idx': CM_MODULE,
        'show_button': True,
        'scheduled_source': 'CM3_scheduled_date',
        'target_date_case_property': 'CM3_form_target'
    },
    {
        'visit_name': _('CM Initial huddle'),
        'xmlns': HUD1,
        'days': 21,
        'module_idx': HUD_MODULE,
        'show_button': True,
        'target_date_case_property': 'HUD1_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 1'),
        'xmlns': CHW1,
        'days': 35,
        'module_idx': CHW_MODULE,
        'show_button': False,
        'scheduled_source': 'CHW1_scheduled_date',
        'target_date_case_property': 'CHW1_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 1'),
        'xmlns': CM4,
        'days': 49,
        'module_idx': CM_MODULE,
        'show_button': True,
        'scheduled_source': 'CM4_scheduled_date',
        'target_date_case_property': 'CM4_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 2'),
        'xmlns': CHW2,
        'days': 100,
        'module_idx': CHW_MODULE,
        'show_button': False,
        'scheduled_source': 'CHW2_scheduled_date',
        'target_date_case_property': 'CHW2_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 2'),
        'xmlns': CM5,
        'days': 130,
        'module_idx': CM_MODULE,
        'show_button': True,
        'scheduled_source': 'CM5_scheduled_date',
        'target_date_case_property': 'CM5_form_target'
    },
    {
        'visit_name': _('CHW CDSMP tracking'),
        'xmlns': CHW4,
        'days': 135,
        'module_idx': CHW_MODULE,
        'show_button': False,
        'scheduled_source': 'CHW4_scheduled_date',
        'target_date_case_property': 'CHW4_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 3'),
        'xmlns': CHW2,
        'days': 200,
        'module_idx': CHW_MODULE,
        'show_button': False,
        'scheduled_source': 'CHW2-2_scheduled_date',
        'target_date_case_property': 'CHW2-2_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 3'),
        'xmlns': CM5,
        'days': 250,
        'module_idx': CM_MODULE,
        'show_button': 'CHW2-2_scheduled_date',
        'scheduled_source': 'CM5-2_scheduled_date',
        'target_date_case_property': 'CM5-2_form_target'
    },
]

LAST_INTERACTION_LIST = [PM1, PM3, CM1, CM3, CM4, CM5, CM6, CHW1, CHW2, CHW3, CHW4]

class DrilldownReportMixin(object):

    report_template_path = ""

    hide_filters = True
    filters = []
    flush_layout = True
    fields = []
    es_results=None

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False
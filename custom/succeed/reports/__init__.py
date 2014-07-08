from django.utils.translation import ugettext as _
from custom.succeed.utils import CONFIG

PM1 = 'http://openrosa.org/formdesigner/111B09EB-DFFA-4613-9A16-A19BA6ED7D04'
PM2 = 'http://openrosa.org/formdesigner/4B52ADB2-AA79-4056-A13E-BB34871876A1'
PM_PM2 = 'http://openrosa.org/formdesigner/31ad9d386120d25238327f0315ada53d9e0f60d9'
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
PD2AM = 'http://openrosa.org/formdesigner/b5376c48fbe845273db04ba88bb610577480fc26'
PD2BPM = 'http://openrosa.org/formdesigner/8fca2fbbbe0655c55d651f587d99368f248842cd'
PD2CHM = 'http://openrosa.org/formdesigner/351ec6c430a7dd90f6f7a96938f3d58183ec3992'
PD2DIABM = 'http://openrosa.org/formdesigner/9e15c3bad39a9f5aea5961c164c7d27d47b555bf'
PD2DEPM = 'http://openrosa.org/formdesigner/40836f5360aad0e4ae84f39dd45d2c205511e73b'
PD2SCM = 'http://openrosa.org/formdesigner/b3226cecdc7c32fe7aca37a76799b48900b2e050'
PD2OM = 'http://openrosa.org/formdesigner/e859b4d46422f61d902be6acd3ed758009694998'
CHW1 = 'http://openrosa.org/formdesigner/4b368b1d73862abeca3bce67b6e09724b8dca850'
CHW1PS = 'http://openrosa.org/formdesigner/40836f5360aad0e4ae84f39dd45d2c205511e73b'
CHW1DIAB = 'http://openrosa.org/formdesigner/2FD5DD7C-38A2-4F46-9386-134C574F7407'
CHW1CHOL = 'http://openrosa.org/formdesigner/351ec6c430a7dd90f6f7a96938f3d58183ec3992'
CHW1SMOKINGSENS = 'http://openrosa.org/formdesigner/937a24202f98f87263a7ecbe5fe8a559dc827a05'
CHW1SL = 'http://openrosa.org/formdesigner/137B1EC0-0DF9-4238-8E7C-0191EF1187AA'
CHW1DIETOBESITY = 'http://openrosa.org/formdesigner/5DE940C5-430B-41AF-8C58-E4C63C49470F'
CHW1COMPREF = 'http://openrosa.org/formdesigner/282DAA4B-6246-43B2-9551-A905C05D8476'
CHW2 = 'http://openrosa.org/formdesigner/cbc4e37437945bfda04e391d11006b6d02c24fc2'
CHW3 = 'http://openrosa.org/formdesigner/5d77815bf7631a527d8647cdbaa5971e367f6548'
CHW4 = 'http://openrosa.org/formdesigner/f8a741808584d772c4b899ef84db197da5b4d12a'
AP2 = 'http://openrosa.org/formdesigner/58ba18b4bd2054419bfa8da8ec2d08f6c547c91b'
CUSTOM_EDIT = 'http://commcarehq.org/cloudcare/custom-edit'
EMPTY_FIELD = "---"

OUTPUT_DATE_FORMAT = "%m/%d/%Y"
INTERACTION_OUTPUT_DATE_FORMAT = "%m/%d/%Y %H:%M"
INPUT_DATE_FORMAT = "%Y-%m-%d"

CM_APP_CM_MODULE = 0
CM_APP_HUD_MODULE = 1
CM_APP_PD_MODULE = 2
CM_APP_CHW_MODULE = 3
CM_APP_APPOINTMENTS_MODULE = 4
CM_APP_MEDICATIONS_MODULE = 5
CM_APP_CREATE_TASK_MODULE = 6
CM_APP_UPDATE_VIEW_TASK_MODULE = 7

PM_APP_PM_MODULE = 0

CHW_APP_ACHW_MODULE = 0
CHW_APP_PD_MODULE = 1
CHW_APP_CHW1_MODULE = 2
CHW_APP_CHW2_MODULE = 3
CHW_APP_CM_MODULE = 4
CHW_APP_MA_MODULE = 5

VISIT_SCHEDULE = [
    {
        'visit_name': _('CM Initial contact form'),
        'xmlns': CM1,
        'days': 5,
        'module_idx': CM_APP_CM_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'CM1_form_target'
    },
    {
        'visit_name': _('CM Medical Record Review'),
        'xmlns': CM2,
        'days': 7,
        'module_idx': CM_APP_CM_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'CM2_form_target'
    },
    {
        'visit_name': _('CM 1-week Telephone Call'),
        'xmlns': CM3,
        'days': 10,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM3_scheduled_date',
        'target_date_case_property': 'CM3_form_target'
    },
    {
        'visit_name': _('CM Initial huddle'),
        'xmlns': HUD1,
        'days': 21,
        'module_idx': CM_APP_HUD_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'HUD1_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 1'),
        'xmlns': CHW1,
        'days': 35,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW1_scheduled_date',
        'target_date_case_property': 'CHW1_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 1'),
        'xmlns': CM4,
        'days': 49,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM4_scheduled_date',
        'target_date_case_property': 'CM4_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 2'),
        'xmlns': CHW2,
        'days': 100,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW2_scheduled_date',
        'target_date_case_property': 'CHW2_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 2'),
        'xmlns': CM5,
        'days': 130,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM5_scheduled_date',
        'target_date_case_property': 'CM5_form_target'
    },
    {
        'visit_name': _('CHW CDSMP tracking'),
        'xmlns': CHW4,
        'days': 135,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW4_scheduled_date',
        'target_date_case_property': 'CHW4_form_target'
    },
    {
        'visit_name': _('CHW Home Visit 3'),
        'xmlns': CHW2,
        'days': 200,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW2-2_scheduled_date',
        'target_date_case_property': 'CHW2-2_form_target'
    },
    {
        'visit_name': _('CM Clinic Visit 3'),
        'xmlns': CM5,
        'days': 250,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': 'CHW2-2_scheduled_date',
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM5-2_scheduled_date',
        'target_date_case_property': 'CM5-2_form_target'
    },
]

SUBMISSION_SELECT_FIELDS = [
    {
        "text": "Project Manager Forms",
        "val": "pm_forms",
        "next": [
            {
                "text": "PM1 Enrollment Form",
                "val": PM1
            },
            {
                "text": "PM2 Edit/Update Patient Info",
                "val": PM2
            },
            {
                "text": "PM3 Disenrollment Form",
                "val": PM3
            },
            {
                "text": "PM4 Change Care Site",
                "val": PM4
            }
        ]
    },
    {
        "text": "Care Manager Forms",
        "val": "cm_forms",
        "next": [
            {
                "text": "CM1 Initial Contact Form",
                "val": CM1
            },
            {
                "text": "CM2 Medical Record Form",
                "val": CM2
            },
            {
                "text": "CM3 1-week Phone Call",
                "val": CM3
            },
            {
                "text": "CM4 Initial Clinic Visit",
                "val": CM4
            },
            {
                "text": "CM5 Follow-up Clinic Visit",
                "val": CM5
            },
            {
                "text": "CM6 Follow-up Phone",
                "val": CM6
            },
            {
                "text": "CM7 Edit Patient Schedule",
                "val": CM7
            }
        ]
    },
    {
        "text": "CHW Forms",
        "val": "chwm_forms",
        "next": [
            {
                "text": "CHW1 Initial Home Visit",
                "val": CHW1
            },
            {
                "text": "CHW1 Psycho-Social",
                "val": CHW1PS
            },
            {
                "text": "CHW1 Cholesterol",
                "val": CHW1CHOL
            },
            {
                "text": "CHW1 Smoking Cessation",
                "val": CHW1SMOKINGSENS
            },
            {
                "text": "CHW1 Stroke Literacy",
                "val": CHW1SL
            },
            {
                "text": "CHW1 Communication Preferences",
                "val": CHW1COMPREF
            },
            {
                "text": "CHW2 Follow-up Home Visit",
                "val": CHW2
            },
            {
                "text": "CHW3 Follow-up Phone",
                "val": CHW3
            },
            {
                "text": "CHW4 CDSMP Tracking",
                "val": CHW4
            }
        ]
    },
    {
        "text": "Patient Data Forms",
        "val": "pd_forms",
        "next": [
            {
                "text": "PD1 Problem List",
                "val": PD1
            },
            {
                "text": "PD2 Medications",
                "val": PD2
            },
            {
                "text": "PD2 Antithrombotic Meds",
                "val": PD2AM
            },
            {
                "text": "PD2 Blood Pressure Meds",
                "val": PD2BPM
            },
            {
                "text": "PD2 Cholesterol Meds",
                "val": PD2CHM
            },
            {
                "text": "PD2 Diabetes Meds",
                "val": PD2DIABM
            },
            {
                "text": "PD2 Depression Meds",
                "val": PD2DEPM
            },
            {
                "text": "PD2 Smoking Cessation Meds",
                "val": PD2SCM
            },
            {
                "text": "PD2 Other Meds",
                "val": PD2OM
            }
        ]
    },
    {
        "text": "Huddle Forms",
        "val": "hd_forms",
        "next": [
            {
                "text": "HUD1 Initial Huddle",
                "val": HUD1
            },
            {
                "text": "HUD2 Follow-up Huddle",
                "val": HUD2
            }
        ]
    }
]

LAST_INTERACTION_LIST = [PM1, PM3, CM1, CM3, CM4, CM5, CM6, CHW1, CHW2, CHW3, CHW4]
MEDICATION_DETAILS = ['MEDS_at_prescribed', 'MEDS_bp_prescribed', 'MEDS_cholesterol_prescribed', 'MEDS_depression_prescribed',
                      'MEDS_diabetes_prescribed', 'MEDS_smoking_prescribed', 'MEDS_other_prescribed']

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
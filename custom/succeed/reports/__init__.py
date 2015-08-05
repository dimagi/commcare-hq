from django.utils.translation import ugettext_lazy as _
from custom.succeed.utils import CONFIG
from dimagi.utils.parsing import ISO_DATE_FORMAT

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
CM6_PHONE = "http://openrosa.org/formdesigner/61e1dc8eae04cf251c96e6d670568471d7954101"
CM7 = 'http://openrosa.org/formdesigner/4b924f784e8dd6a23045649730e82f6a2e7ce7cf'
CM_NEW_TASK = 'http://openrosa.org/formdesigner/BBDEBCBD-5EC6-47F9-A8E3-5CCF74AB9EFE'
CM_UPDATE_TASK = 'http://openrosa.org/formdesigner/2447a22e4a648d5510db9a4db65f3b60ac91ed98'
HUD1 = 'http://openrosa.org/formdesigner/24433229c5f25d0bd3ceee9bf70c72093056d1af'
HUD2 = 'http://openrosa.org/formdesigner/63f8287ac6e7dce0292ebac9b232b0d3bde327dc'
PD1 = 'http://openrosa.org/formdesigner/9eb0eaf6954791425d6d5f0b66db9a484cacd264'
PD2 = 'http://openrosa.org/formdesigner/69751bf3078369491e1c2f1e3c874895f762a4c1'
PD2ALL = "http://openrosa.org/formdesigner/39C22C58-3440-4D6B-92EF-846B07686F54"
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
CQ = "http://openrosa.org/formdesigner/bbbb340e75d2f0199b996e0b8b27984994663949"
AS = "http://openrosa.org/formdesigner/DE075E90-E505-48DF-B963-A66E7CE192D4"
TRANS = "http://openrosa.org/formdesigner/A0014589-AEAE-4636-96A8-E347A3219AF4"
HBP = "http://openrosa.org/formdesigner/5489CDF8-35E9-4A47-A88B-1839BBA25485"
PAFSHS = "http://openrosa.org/formdesigner/4D48CEAD-86AC-4549-88A5-4F669BCD2FB6"
NAV = "http://openrosa.org/formdesigner/363a3fd625bbae3e01b855d127f8fd6c1a6636b3"
CHW3_PHONE = "http://openrosa.org/formdesigner/f426d05877891c696b061f4f039baf0a84f237d1"
AP1 = "http://openrosa.org/formdesigner/ef1f6eb52a38edeb962e2b4e526a5d0fef57fdbe"
AP1_ADD = "http://openrosa.org/formdesigner/56b60d6c99f8e3bcfdbbd72256c47ab015a9f4a3"
UPDATE_TASK_ALL = "http://openrosa.org/formdesigner/e03e28280756e22d7a94af52825bdba7b3a3dd7f"

CUSTOM_EDIT = 'http://commcarehq.org/cloudcare/custom-edit'
EMPTY_FIELD = "---"

OUTPUT_DATE_FORMAT = "%m/%d/%Y"
INTERACTION_OUTPUT_DATE_FORMAT = "%m/%d/%Y %H:%M"
INPUT_DATE_FORMAT = ISO_DATE_FORMAT

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
CHW_APP_TASK_MODULE = 6
CHW_ADD_APPOINTMENTS_MODULE = 4

VISIT_SCHEDULE = [
    {
        'visit_name': _('CM Initial contact form'),
        'xmlns': CM1,
        'days': 5,
        'module_idx': CM_APP_CM_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'CM1_form_target',
        'completed_date': ['CM1_form_completed'],
        'ignored_field': 'CM1_form_ignore',
        'completion_field': 'CM1_form_completed'
    },
    {
        'visit_name': _('CM Medical Record Review'),
        'xmlns': CM2,
        'days': 7,
        'module_idx': CM_APP_CM_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'CM2_form_target',
        'completed_date': ['CM2_form_completed'],
        'ignored_field': 'CM2_form_ignore',
        'completion_field': 'CM2_form_completed'
    },
    {
        'visit_name': _('CM 1-week Telephone Call'),
        'xmlns': CM3,
        'days': 10,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM3_scheduled_date',
        'target_date_case_property': 'CM3_form_target',
        'completed_date': ['CM3_form_completed'],
        'ignored_field': 'CM3_form_ignore',
        'completion_field': 'CM3_form_completed'
    },
    {
        'visit_name': _('CM Initial huddle'),
        'xmlns': HUD1,
        'days': 21,
        'module_idx': CM_APP_HUD_MODULE,
        'responsible_party': CONFIG['cm_role'],
        'show_button': True,
        'target_date_case_property': 'HUD1_form_target',
        'completed_date': ['HUD1_form_completed'],
        'ignored_field': 'HUD1_form_ignore',
        'completion_field': 'HUD1_form_completed'
    },
    {
        'visit_name': _('CHW Home Visit 1'),
        'xmlns': CHW1,
        'days': 35,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW1_scheduled_date',
        'target_date_case_property': 'CHW1_form_target',
        'completed_date': ['CHW1_1_complete', 'CHW1_1_complete_date'],
        'ignored_field': 'CHW1_form_ignore',
        'completion_field': 'CHW1_1_complete_date'
    },
    {
        'visit_name': _('CM Clinic Visit 1'),
        'xmlns': CM4,
        'days': 49,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM4_scheduled_date',
        'target_date_case_property': 'CM4_1_form_target',
        'completed_date': ['CM4_1_complete', 'CM4_1_complete_date'],
        'ignored_field': 'CM4_form_ignore',
        'completion_field': 'CM4_1_complete_date'
    },
    {
        'visit_name': _('CHW Home Visit 2'),
        'xmlns': CHW2,
        'days': 100,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW1_2_scheduled_date',
        'target_date_case_property': 'CHW1_2_form_target',
        'completed_date': ['CHW1_2_complete', 'CHW1_2_complete_date'],
        'ignored_field': 'CHW2_form_ignore',
        'completion_field': 'CHW1_2_complete_date'
    },
    {
        'visit_name': _('CM Clinic Visit 2'),
        'xmlns': CM4,
        'days': 130,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': True,
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM4_2_scheduled_date',
        'target_date_case_property': 'CM4_2_form_target',
        'completed_date': ['CM4_2_complete', 'CM4_2_complete_date'],
        'ignored_field': 'CM5_form_ignore',
        'completion_field': 'CM4_2_complete_date'
    },
    {
        'visit_name': _('CHW CDSMP tracking'),
        'xmlns': CHW4,
        'days': 135,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'target_date_case_property': 'CHW4_form_target',
        'completed_date': ['CHW4_form_completed'],
        'ignored_field': 'CHW4_form_ignore',
        'completion_field': 'CHW4_form_completed'
    },
    {
        'visit_name': _('CHW Home Visit 3'),
        'xmlns': CHW2,
        'days': 200,
        'module_idx': CM_APP_CHW_MODULE,
        'show_button': False,
        'responsible_party': CONFIG['chw_role'],
        'scheduled_source': 'CHW1_3_scheduled_date',
        'target_date_case_property': 'CHW1_3_form_target',
        'completed_date': ['CHW1_3_complete', 'CHW1_3_complete_date'],
        'ignored_field': 'CHW2-2_form_ignore',
        'completion_field': 'CHW1_3_complete_date'
    },
    {
        'visit_name': _('CM Clinic Visit 3'),
        'xmlns': CM4,
        'days': 250,
        'module_idx': CM_APP_CM_MODULE,
        'show_button': 'CHW2-2_scheduled_date',
        'responsible_party': CONFIG['cm_role'],
        'scheduled_source': 'CM4_3_scheduled_date',
        'target_date_case_property': 'CM4_3_form_target',
        'completed_date': ['CM4_3_complete', 'CM4_3_complete_date'],
        'ignored_field': 'CM5-2_form_ignore',
        'completion_field': 'CM4_3_complete_date'
    },
]

SUBMISSION_SELECT_FIELDS = {
    'pm_forms': [PM1, PM3, PM4, PM_PM2, CHW4],
    'cm_forms': [CM1, CM2, CM3, CM4, CM6_PHONE, CM7, HUD1, PD1, PD2AM, PD2BPM,
                 PD2CHM, PD2DIABM, PD2DEPM, PD2SCM, PD2OM, PD2ALL],
    'chw_forms': [CQ, CHW1PS, AS, CHW1DIAB, CHW1CHOL, CHW1SMOKINGSENS, TRANS,
                  CHW1SL, HBP, CHW1DIETOBESITY, PAFSHS, NAV, CHW1COMPREF, CHW3_PHONE, CHW4],
    'task': [AP1, AP2, CM_NEW_TASK, CM_UPDATE_TASK, AP1_ADD, UPDATE_TASK_ALL]
}

LAST_INTERACTION_LIST = [PM1, PM3, CM1, CM3, CM4, CM5, CM6, CHW1, CHW2, CHW3, CHW4]
MEDICATION_DETAILS = ['MEDS_at_prescribed', 'MEDS_bp_prescribed', 'MEDS_cholesterol_prescribed', 'MEDS_depression_prescribed',
                      'MEDS_diabetes_prescribed', 'MEDS_smoking_prescribed', 'MEDS_other_prescribed']

TASK_RISK_FACTOR = {
    "stroke_literacy": "Stroke Literacy",
    "blood_pressure": "Blood Pressure",
    "cholesterol": "Cholesterol",
    "diabetes": "Diabetes",
    "psycho-social": "Psycho/social",
    "healthy-eating": "Healthy Eating",
    "physical_activity": "Physical activity",
    "transportation": "Transportation",
    "insurance": "Access to Insurance",
    "alcohol-drug": "Alcohol and Drug Use",
    "medication": "Medication Management",
    "general": "General"
}


TASK_ACTIVITY = {
    "review": "Review",
    "call": "Call",
    "clinic_visit": "Clinic Visit",
    "home_visit": "Home Visit",
    "huddle_action": "Huddle Action",
    "medication": "Medication",
    "medication_adjustment" : "Medication Adjustment",
    "order_lab": "Order Lab",
    "review_lab": "Review Lab",
    "make_referral": "Make Referral",
    "mail_document": "Mail Document(s)",
    "visit_preparation": "Visit Preparation"
}

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

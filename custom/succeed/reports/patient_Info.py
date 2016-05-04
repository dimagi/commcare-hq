from custom.succeed.reports import OUTPUT_DATE_FORMAT, CM2, PM_PM2, PM2, CHW_APP_PD_MODULE, CM_APP_PD_MODULE,\
    PM_APP_PM_MODULE, AP2, CM_APP_APPOINTMENTS_MODULE
from django.utils.translation import ugettext as _
from custom.succeed.reports.patient_details import PatientDetailsReport
from custom.succeed.utils import get_form_dict, is_pm_or_pi, is_cm, is_chw
from custom.succeed.utils import format_date

EMPTY_FIELD = ""


class PatientInfoDisplay(object):

    def __init__(self, case):
        self.case = case
        super(PatientInfoDisplay, self).__init__()

    #  helper functions

    def get_diagnosis(self):
        diagnosis = getattr(self.case, 'diagnosis', EMPTY_FIELD)
        if diagnosis == 'ischemic_stroke':
            return _('Ischemic Stroke')
        if diagnosis == 'tia':
            return _('Transient Ischemic Attack (TIA)')
        if diagnosis == 'intracerebral_hemorrhage':
            return _('Intracerebral Hemorrhage')
        return diagnosis

    def get_preferred_language(self):
        preferred_languge = getattr(self.case, 'preferred_language', EMPTY_FIELD)
        if preferred_languge == 'Other':
            return getattr(self.case, 'preferred_language_other', EMPTY_FIELD)
        else:
            return preferred_languge

    def get_phone_data(self, number):
        return {'label':_('Phone Number %s' % number),
                'value': [
                  _("Number: ") + getattr(self.case, 'phone_%s' % number, EMPTY_FIELD),
                  _("Type: ") + getattr(self.case, 'phone_%s_type' % number, EMPTY_FIELD),
                  _("Best time to call: ") + getattr(self.case, 'phone_%s_time' % number, EMPTY_FIELD),
                  _("Can receive text messages? ") + getattr(self.case, 'phone_%s_text' % number, EMPTY_FIELD)
                ]}

    def get_family_member(self, number):
        return {'label': _('Family Member %s' % number),
                'value': [
                  _("Name: ") + getattr(self.case, 'ff%s_name' % number, EMPTY_FIELD),
                  _("Relationship: ") + getattr(self.case, 'ff%s_relationship' % number, EMPTY_FIELD),
                  _("Phone number: ") + getattr(self.case, 'ff%s_number' % number, EMPTY_FIELD)
                ]}

    def get_recent_blood_pressure(self, number):
        CM2_form_dict = get_form_dict(self.case, CM2)
        blood_pressure = dict()
        if CM2_form_dict is not None and 'CM2_bp_%s_group' % number in CM2_form_dict:
            group = 'CM2_bp_%s_group' % number
            blood_pressure['CM2_bp_%s_sbp' % number] = CM2_form_dict[group].get('CM2_bp_%s_sbp' % number, EMPTY_FIELD) \
                                                       + '/' + CM2_form_dict[group].get('CM2_bp_%s_dbp' % number, EMPTY_FIELD)
            blood_pressure['CM2_patient_bp_%s_date' % number] = format_date(CM2_form_dict[group].get('CM2_patient_bp_%s_date' % number, EMPTY_FIELD), OUTPUT_DATE_FORMAT)

        return {'label': _('Recent Blood Pressure %s' % number),
                'value': [
                  _("Value: ") + blood_pressure.get('CM2_bp_%s_sbp' % number, EMPTY_FIELD),
                  _("Date: ") + blood_pressure.get('CM2_patient_bp_%s_date' % number, EMPTY_FIELD)
                ]}

    def get_baseline_LDL(self):
        CM2_form_dict = get_form_dict(self.case, CM2)
        baseline_LDL = dict()
        if CM2_form_dict is not None and 'CM2_LDL_group' in CM2_form_dict:
            baseline_LDL['lab_LDL'] = CM2_form_dict['CM2_LDL_group'].get('CM2_lab_LDL', EMPTY_FIELD)
            baseline_LDL['lab_LDL_date'] = format_date(CM2_form_dict['CM2_LDL_group'].get('CM2_lab_LDL_date', EMPTY_FIELD), OUTPUT_DATE_FORMAT)
            baseline_LDL['lab_LDL_fasting'] = CM2_form_dict['CM2_LDL_group'].get('CM2_lab_LDL_fasting', EMPTY_FIELD)
            baseline_LDL['lab_LDL_statin'] = CM2_form_dict['CM2_LDL_group'].get('CM2_lab_LDL_statin', EMPTY_FIELD)

        return {'label': _('Baseline LDL'),
                'value': [
                  _("Value: ") + baseline_LDL.get('lab_LDL', EMPTY_FIELD),
                  _("Date: ") + baseline_LDL.get('lab_LDL_date', EMPTY_FIELD),
                  _("Fasting? ") + baseline_LDL.get('lab_LDL_fasting', EMPTY_FIELD),
                  _("Taking statin at time of draw? ") + baseline_LDL.get('lab_LDL_statin', EMPTY_FIELD),
                ]}

    @property
    def general_information(self):
        general_info = {}
        general_info['mrn'] = {'label': _('MRN'), 'value': getattr(self.case, 'mrn', EMPTY_FIELD)}
        general_info['gender'] = {'label': _('Gender'), 'value':getattr(self.case, 'gender', EMPTY_FIELD)}
        general_info['randomization_date'] = {'label': _('Randomization Date'),
                                              'value': format_date(getattr(self.case, 'randomization_date', EMPTY_FIELD), OUTPUT_DATE_FORMAT)}

        general_info['diagnosis'] = {'label': _('Diagnosis'), 'value': self.get_diagnosis()}
        general_info['age'] = {'label': _('Age'), 'value': getattr(self.case, 'age', EMPTY_FIELD)}

        general_info['preferred_language'] = {'label': _('Preferred Language'), 'value': self.get_preferred_language()}
        general_info['primary_care_provider'] = {'label': _('Primary Care Provider'),
                                                 'value': [
                                                         getattr(self.case, 'PCP_name', EMPTY_FIELD),
                                                         getattr(self.case, 'PCP_organization', EMPTY_FIELD),
                                                         getattr(self.case, 'PCP_address', EMPTY_FIELD),
                                                         getattr(self.case, 'PCP_telephone', EMPTY_FIELD),
                                                     ]}

        general_info['key_notes'] = {'label': _('Key Notes'),
                                     'value': getattr(self.case, 'key_notes', EMPTY_FIELD)}

        general_info['running_notes'] = {'label': _('Running Notes'),
                                         'value': getattr(self.case, 'notes', EMPTY_FIELD)}

        general_info['cdsmp_notes'] = {'label': _('CDSMP Notes'),
                                       'value': getattr(self.case, 'cdsmp_notes', EMPTY_FIELD)}
        return general_info

    @property
    def contact_information(self):
        contact_info = {}
        contact_info['address'] = {'label': _('Address'),
                                   'value': [
                                        getattr(self.case, 'address_street', EMPTY_FIELD),
                                        getattr(self.case, 'address_street2', EMPTY_FIELD),
                                        getattr(self.case, 'address_city', EMPTY_FIELD) + ', ' +
                                        getattr(self.case, 'address_state', EMPTY_FIELD) + ' ' +
                                        getattr(self.case, 'address_zip', EMPTY_FIELD)
                                   ]}

        for i in range(1, 4):
            contact_info['phone_number_%s' % i] = self.get_phone_data(i)
        for i in range(1, 5):
            contact_info['family_member_%s' % i] = self.get_family_member(i)

        return contact_info

    @property
    def most_recent_lab_exams(self):
        most_recent_lab_exams = {}
        for i in range(1, 4):
            most_recent_lab_exams['recent_blood_pressure_%s' % i] = self.get_recent_blood_pressure(i)

        def _get_field_value(label, value, is_date=None):
            val = getattr(self.case, value, EMPTY_FIELD)
            if val and is_date:
                val = format_date(val, OUTPUT_DATE_FORMAT)
            return _(label) + ': ' + str(val)

        most_recent_lab_exams['bmi'] = {'label': _('BMI'),
                                        'value': [_get_field_value('BMI Value', 'BMI'),
                                                  _get_field_value('BMI Category', 'BMI_category'),
                                                  _get_field_value('Date of weighing', 'BMI_date', is_date=True)]}
        most_recent_lab_exams['waist_circumference'] = {'label': _('Waist Circumference'),
                                                        'value': [_get_field_value('Value', 'waist_circumference'),
                                                                  _get_field_value('Date', 'waist_circumference_date', is_date=True)
                                                        ]}
        most_recent_lab_exams['most_recent_HbA1c'] = {'label': _('Most Recent HbA1c'),
                                                      'value': [_get_field_value('Value', 'lab_HbA1c'),
                                                                _get_field_value('Date', 'lab_HbA1c_date', is_date=True)]}
        most_recent_lab_exams['baseline_LDL'] = self.get_baseline_LDL()
        most_recent_lab_exams['most_recent_LDL'] = {'label': _('Most Recent LDL'),
                                                    'value': [_get_field_value('Value', 'lab_HDL'),
                                                              _get_field_value('Date', 'lab_HDL_date', is_date=True)]}
        most_recent_lab_exams['most_recent_HDL'] = {'label': _('Most Recent HDL'),
                                                    'value': [_get_field_value('Value', 'lab_HDL'),
                                                              _get_field_value('Date', 'lab_HDL_date', is_date=True)]}
        most_recent_lab_exams['most_recent_Triglycerides'] = {'label': _('Most Recent Triglycerides'),
                                                              'value': [_get_field_value('Value', 'lab_triglycerides'),
                                                                        _get_field_value('Date', 'lab_triglycerides_date', is_date=True)]}
        most_recent_lab_exams['most_recent_INR'] = {'label': _('Most Recent INR'),
                                                    'value': [_get_field_value('Value', 'lab_INR'),
                                                              _get_field_value('Date', 'lab_INR_date', is_date=True)]}

        return most_recent_lab_exams

    @property
    def allergies(self):
        allergies = {}
        allergies['statin'] = {'label': _('Statin'), 'value': getattr(self.case, 'allergy_statin', EMPTY_FIELD)}
        allergies['aspirin'] = {'label': _('Aspirin'), 'value': getattr(self.case, 'allergy_aspirin', EMPTY_FIELD)}
        allergies['other'] = {'label': _('Other'), 'value': getattr(self.case, 'allergy_other_list', EMPTY_FIELD)}
        return allergies


class PatientInfoReport(PatientDetailsReport):
    slug = "patient_info"
    name = 'Patient Info'

    @property
    def report_context(self):
        self.report_template_path = "patient_info.html"
        ret = super(PatientInfoReport, self).report_context
        self.update_app_info()
        ret['view_mode'] = 'info'
        patient_info = PatientInfoDisplay(ret['patient'])

        #  check user role:
        user = self.request.couch_user
        if is_pm_or_pi(user):
            ret['edit_patient_info_url'] = self.get_form_url(self.pm_app_dict,
                                                             self.latest_pm_build, PM_APP_PM_MODULE,
                                                             PM_PM2, ret['patient']['_id'])
        elif is_cm(user):
            ret['edit_patient_info_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                             CM_APP_PD_MODULE, PM_PM2, ret['patient']['_id'])
        elif is_chw(user):
            ret['edit_patient_info_url'] = self.get_form_url(self.chw_app_dict, self.latest_chw_build,
                                                             CHW_APP_PD_MODULE, PM2, ret['patient']['_id'])

        ret['upcoming_appointments_url'] = None
        if is_cm(user):
            ret['upcoming_appointments_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                                 CM_APP_APPOINTMENTS_MODULE, AP2,
                                                                 parent_id=ret['patient']['_id'])

        ret['general_information'] = patient_info.general_information
        ret['contact_information'] = patient_info.contact_information
        ret['most_recent_lab_exams'] = patient_info.most_recent_lab_exams
        ret['allergies'] = patient_info.allergies
        return ret

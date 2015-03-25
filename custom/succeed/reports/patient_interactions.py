from collections import OrderedDict
from django.utils import html
from corehq.apps.users.models import CouchUser
from custom.succeed.reports.patient_task_list import PatientTaskListReport
from custom.succeed.reports import *
from custom.succeed.reports.patient_details import PatientDetailsReport
from dimagi.utils.decorators.memoized import memoized
from custom.succeed.utils import is_cm, is_chw

RISK_FACTOR_CONFIG = OrderedDict()
RISK_FACTOR_CONFIG['Status:'] = ['risk-factor_at_status', 'risk-factor_bp_status',
                                 'risk-factor_cholesterol_status', 'risk-factor_psycho-social_status',
                                 'risk-factor_diabetes_status', 'risk-factor_smoking_status']
RISK_FACTOR_CONFIG['CHW Protocol Indicated:'] = ['risk-factor_at_chw', 'risk-factor_bp_chw',
                                                 'risk-factor_cholesterol_chw', 'risk-factor_psycho-social_chw',
                                                 'risk-factor_diabetes_chw', 'risk-factor_smoking_chw']
RISK_FACTOR_CONFIG['CHW  Protocol Count:'] = ['CHW_antithrombotic_count', 'CHW_bp_count', 'CHW_cholesterol_count',
                                              'CHW_psycho-social_count', 'CHW_diabetes_count', 'CHW_smoking_count']
RISK_FACTOR_CONFIG['Notes:'] = ['risk-factor_at_notes', 'risk-factor_bp_notes', 'risk-factor_cholesterol_notes',
                                'risk-factor_psycho-social_notes', 'risk-factor_diabetes_notes',
                                'risk-factor_smoking_notes']


class PatientInteractionsReport(PatientDetailsReport):
    slug = "patient_interactions"
    name = 'Patient Interactions'

    @property
    def report_context(self):
        self.report_template_path = "patient_interactions.html"
        ret = super(PatientInteractionsReport, self).report_context
        self.update_app_info()

        ret['view_mode'] = 'interactions'
        ret['problem_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                               CM_APP_PD_MODULE, PD1, ret['patient']['_id'])
        ret['huddle_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                              CM_APP_HUD_MODULE, HUD2, ret['patient']['_id'])
        ret['cm_phone_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                CM_APP_CM_MODULE, CM6_PHONE, ret['patient']['_id'])
        ret['cm_visits_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                 CM_APP_CM_MODULE, CM4, ret['patient']['_id'])

        ret['anti_thrombotic_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                       CM_APP_MEDICATIONS_MODULE, PD2AM, ret['patient']['_id'])
        ret['blood_pressure_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                      CM_APP_MEDICATIONS_MODULE, PD2BPM, ret['patient']['_id'])
        ret['cholesterol_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                   CM_APP_MEDICATIONS_MODULE, PD2CHM, ret['patient']['_id'])
        ret['diabetes_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                CM_APP_MEDICATIONS_MODULE, PD2DIABM, ret['patient']['_id'])
        ret['depression_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                  CM_APP_MEDICATIONS_MODULE, PD2DEPM, ret['patient']['_id'])
        ret['smoking_cessation_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                         CM_APP_MEDICATIONS_MODULE, PD2SCM, ret['patient']['_id'])
        ret['other_meds_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                  CM_APP_MEDICATIONS_MODULE, PD2OM, ret['patient']['_id'])

        ret['interaction_table'] = []
        for visit_key, visit in enumerate(VISIT_SCHEDULE):
            if visit['target_date_case_property'] in ret['patient'] and \
                    ret['patient'][visit['target_date_case_property']]:
                try:
                    target_date = (ret['patient'][visit['target_date_case_property']])
                except TypeError:
                    target_date = _("Bad Date Format!")
            else:
                target_date = EMPTY_FIELD

            received_date = EMPTY_FIELD
            for completed in visit['completed_date']:
                if completed in ret['patient']:
                    received_date = ret['patient'][completed]

            schedulet_date = EMPTY_FIELD
            if 'scheduled_source' in visit and ret['patient'].get_case_property(visit['scheduled_source']):
                schedulet_date = ret['patient'].get_case_property(visit['scheduled_source'])

            interaction = {
                'url': '',
                'name': visit['visit_name'],
                'target_date': target_date,
                'received_date': received_date,
                'completed_by': EMPTY_FIELD,
                'scheduled_date': schedulet_date
            }

            if visit['show_button']:
                interaction['url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                       visit['module_idx'], visit['xmlns'], ret['patient']['_id'])


            ret['interaction_table'].append(interaction)

            medication = []
            for med_prop in MEDICATION_DETAILS:
                medication.append(getattr(ret['patient'], med_prop, EMPTY_FIELD))
            ret['medication_table'] = medication

        user = self.request.couch_user
        ret['patient_task_list_url'] = html.escape(
            PatientTaskListReport.get_url(*[ret['patient']["domain"]]) +
            "?patient_id=%s&task_status=%s" % (ret['patient']["_id"], "open"))
        if is_cm(user):
            ret['create_new_task_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                           CM_APP_CREATE_TASK_MODULE, CM_NEW_TASK,
                                                           ret['patient']['_id'])
        elif is_chw(user):
            ret['create_new_task_url'] = self.get_form_url(self.chw_app_dict, self.latest_chw_build,
                                                           CHW_APP_TASK_MODULE, CM_NEW_TASK, ret['patient']['_id'])

        ret['view_appointments_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                         CM_APP_APPOINTMENTS_MODULE, AP2,
                                                         parent_id=ret['patient']['_id'])
        ret['add_appointments_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build,
                                                        CM_APP_PD_MODULE, AP1,
                                                        case_id=ret['patient']['_id'])

        # Risk Factor Table
        rows = []
        for key, val in RISK_FACTOR_CONFIG.iteritems():
            data = [key]
            for v in val:
                case_data = ret['patient'][v] if v in ret['patient'] else ''
                if key == 'Status:':
                    if case_data:
                        case_data = case_data.replace('-', ' ').title()
                    else:
                        case_data = EMPTY_FIELD
                data.append(case_data)
            rows.append(data)

        ret['risk_factor_table'] = rows
        return ret

    @memoized
    def get_user(self, user_id):
        return CouchUser.get(user_id)
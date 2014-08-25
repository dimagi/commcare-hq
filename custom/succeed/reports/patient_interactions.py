from couchdbkit.exceptions import ResourceNotFound
from datetime import timedelta
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.users.models import CouchUser
from custom.succeed.reports import *
from custom.succeed.reports.patient_details import PatientDetailsReport
from dimagi.utils.decorators.memoized import memoized
from custom.succeed.utils import format_date


class PatientInteractionsReport(PatientDetailsReport):
    slug = "patient_interactions"
    name = 'Patient Interactions'

    @property
    def report_context(self):
        self.report_template_path = "patient_interactions.html"
        ret = super(PatientInteractionsReport, self).report_context
        ret['view_mode'] = 'interactions'
        ret['problem_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_PD_MODULE, PD1, ret['patient']['_id'])
        ret['huddle_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_HUD_MODULE, HUD2, ret['patient']['_id'])
        ret['cm_phone_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_CM_MODULE, CM6, ret['patient']['_id'])
        ret['chw_phone_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_CHW_MODULE, CHW3, ret['patient']['_id'])
        ret['cm_visits_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_APPOINTMENTS_MODULE, AP2, ret['patient']['_id'])

        ret['anti_thrombotic_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2AM, ret['patient']['_id'])
        ret['blood_pressure_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2BPM, ret['patient']['_id'])
        ret['cholesterol_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2CHM, ret['patient']['_id'])
        ret['depression_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2DIABM, ret['patient']['_id'])
        ret['diabetes_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2DEPM, ret['patient']['_id'])
        ret['smoking_cessation_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2SCM, ret['patient']['_id'])
        ret['other_meds_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2OM, ret['patient']['_id'])

        ret['interaction_table'] = []
        for visit_key, visit in enumerate(VISIT_SCHEDULE):
            if ret['patient']["randomization_date"]:
                try:
                    target_date = (ret['patient']["randomization_date"] + timedelta(days=visit['days'])).strftime(OUTPUT_DATE_FORMAT)
                except TypeError:
                    target_date = _("Bad Date Format!")
            else:
                target_date = EMPTY_FIELD
            interaction = {
                'url': '',
                'name': visit['visit_name'],
                'target_date': target_date,
                'received_date': EMPTY_FIELD,
                'completed_by': EMPTY_FIELD,
                'scheduled_date': EMPTY_FIELD
            }
            for key, action in enumerate(ret['patient']['actions']):
                if visit['xmlns'] == action['xform_xmlns']:
                    interaction['received_date'] = action['date'].strftime(INTERACTION_OUTPUT_DATE_FORMAT)
                    try:
                        user = self.get_user(action['user_id'])
                        interaction['completed_by'] = user.human_friendly_name
                    except ResourceNotFound:
                        interaction['completed_by'] = EMPTY_FIELD
                    del ret['patient']['actions'][key]
                    break
            if visit['show_button']:
                interaction['url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, visit['module_idx'], visit['xmlns'], ret['patient']['_id'])
            if 'scheduled_source' in visit and ret['patient'].get_case_property(visit['scheduled_source']):
                interaction['scheduled_date'] = format_date(ret['patient'].get_case_property(visit['scheduled_source']), INTERACTION_OUTPUT_DATE_FORMAT, localize=True)

            ret['interaction_table'].append(interaction)

            medication = []
            for med_prop in MEDICATION_DETAILS:
                medication.append(getattr(ret['patient'], med_prop, EMPTY_FIELD))
            ret['medication_table'] = medication
        return ret

    @memoized
    def get_user(self, user_id):
        return CouchUser.get(user_id)
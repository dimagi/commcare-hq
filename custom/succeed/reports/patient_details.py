from datetime import datetime, timedelta
from couchdbkit.exceptions import ResourceNotFound
from django.http.response import Http404
from django.utils import html
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import CustomProjectReport
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CouchUser
from custom.succeed.reports import DrilldownReportMixin, VISIT_SCHEDULE, CM_APP_PD_MODULE, CM_APP_HUD_MODULE, CM_APP_CM_MODULE, CM_APP_CHW_MODULE, \
    EMPTY_FIELD, OUTPUT_DATE_FORMAT, INPUT_DATE_FORMAT, PM2, PM_APP_PM_MODULE, CHW_APP_MA_MODULE, CHW_APP_PD_MODULE
from custom.succeed.reports import PD1, PD2, HUD2, CM6, CHW3
from custom.succeed.reports.patient_Info import PatientInfoDisplay
from custom.succeed.utils import SUCCEED_CM_APPNAME, is_pm_or_pi, is_cm, SUCCEED_PM_APPNAME, SUCCEED_CHW_APPNAME, is_chw



class PatientInfoReport(CustomProjectReport, DrilldownReportMixin, ElasticProjectInspectionReport):
    slug = "patient"

    hide_filters = True
    filters = []
    ajax_pagination = True

    default_sort = {
        "received_on": "desc"
    }

    name = "Patient Info"

    def get_case(self):
        if self.request.GET.get('patient_id', None) is None:
            return None
        return CommCareCase.get(self.request.GET['patient_id'])

    @property
    def report_context(self):
        ret = {}

        try:
            case = self.get_case()
            has_error = False
        except ResourceNotFound:
            has_error = True
            case = None

        if case is None:
            self.report_template_path = "error.html"
            if has_error:
                ret['error_message'] = "Patient not found"
            else:
                ret['error_message'] = "No patient selected"
            return ret


        def get_form_url(app_dict, app_build_id, module_idx, form, case_id=None):
            try:
                module = app_dict['modules'][module_idx]
                form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == form][0]
            except IndexError:
                return ''

            return html.escape(get_cloudcare_form_url(domain=self.domain,
                                                      app_build_id=app_build_id,
                                                      module_id=CM_APP_CM_MODULE,
                                                      form_id=form_idx,
                                                      case_id=case_id))


        try:
            cm_app_dict = get_cloudcare_app(case['domain'], SUCCEED_CM_APPNAME)
            latest_cm_build = ApplicationBase.get_latest_build(case['domain'], cm_app_dict['_id'])['_id']
            pm_app_dict = get_cloudcare_app(case['domain'], SUCCEED_PM_APPNAME)
            latest_pm_build = ApplicationBase.get_latest_build(case['domain'], pm_app_dict['_id'])['_id']
            chw_app_dict = get_cloudcare_app(case['domain'], SUCCEED_CHW_APPNAME)
            latest_chw_build = ApplicationBase.get_latest_build(case['domain'], chw_app_dict['_id'])['_id']
        except ResourceNotFound as ex:
            self.report_template_path = "error.html"
            ret['error_message'] = ex.message
            return ret

        view_mode = self.request.GET.get('view', 'info')
        ret['patient'] = case
        ret['root_url'] = '?patient_id=%s' % case['_id']
        ret['view_mode'] = view_mode

        if view_mode == 'info':
            self.report_template_path = "patient_info.html"
            patient_info = PatientInfoDisplay(case)

            #  check user role:
            user = self.request.couch_user
            if is_pm_or_pi(user):
                ret['edit_patient_info_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM2)
            elif is_cm(user):
                ret['edit_patient_info_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PM2)
            elif is_chw(user):
                ret['edit_patient_info_url'] = get_form_url(chw_app_dict, latest_chw_build, CHW_APP_PD_MODULE, PM2)

            if is_pm_or_pi(user):
                ret['upcoming_appointments_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM2)
            elif is_cm(user):
                ret['upcoming_appointments_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PM2)
            elif is_chw(user):
                ret['upcoming_appointments_url'] = get_form_url(chw_app_dict, latest_chw_build, CHW_APP_MA_MODULE, PM2)

            ret['general_information'] = patient_info.general_information
            ret['contact_information'] = patient_info.contact_information
            ret['most_recent_lab_exams'] = patient_info.most_recent_lab_exams
            ret['allergies'] = patient_info.allergies

        elif view_mode == 'submissions':
            self.report_template_path = "patient_submissions.html"
        elif view_mode == 'interactions':
            self.report_template_path = "patient_interactions.html"
            ret['problem_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PD1)
            ret['medication_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PD2)
            ret['huddle_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_HUD_MODULE, HUD2)
            ret['cm_phone_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_CM_MODULE, CM6)
            ret['chw_phone_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_CHW_MODULE, CHW3)
            ret['interaction_table'] = []
            for visit_key, visit in enumerate(VISIT_SCHEDULE):
                if case["randomization_date"]:
                    target_date = (case["randomization_date"] + timedelta(days=visit['days'])).strftime(OUTPUT_DATE_FORMAT)
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
                for key, action in enumerate(case['actions']):
                    if visit['xmlns'] == action['xform_xmlns']:
                        interaction['received_date'] = action['date'].strftime(OUTPUT_DATE_FORMAT)
                        try:
                            user = CouchUser.get(action['user_id'])
                            interaction['completed_by'] = user.raw_username
                        except ResourceNotFound:
                            interaction['completed_by'] = EMPTY_FIELD
                        del case['actions'][key]
                        break
                if visit['show_button']:
                    interaction['url'] = get_form_url(cm_app_dict, latest_cm_build, visit['module_idx'], visit['xmlns'])
                if 'scheduled_source' in visit and case.get_case_property(visit['scheduled_source']):
                    interaction['scheduled_date'] = (case.get_case_property(visit['scheduled_source'])).strftime(OUTPUT_DATE_FORMAT)

                ret['interaction_table'].append(interaction)

        elif view_mode == 'plan':
            self.report_template_path = "patient_plan.html"
        elif view_mode == 'status':
            self.report_template_path = "patient_status.html"
        else:
            raise Http404
        return ret

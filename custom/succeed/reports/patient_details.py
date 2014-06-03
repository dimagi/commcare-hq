from datetime import datetime, timedelta
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http.response import Http404
from django.utils import html
from corehq.apps.api.es import ReportXFormES
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CouchUser, CommCareUser
from custom.succeed.reports import DrilldownReportMixin, VISIT_SCHEDULE, CM_APP_PD_MODULE, CM_APP_HUD_MODULE, CM_APP_CM_MODULE, CM_APP_CHW_MODULE, \
    EMPTY_FIELD, OUTPUT_DATE_FORMAT, INPUT_DATE_FORMAT, PM2, PM_APP_PM_MODULE, CHW_APP_MA_MODULE, CHW_APP_PD_MODULE, SUBMISSION_SELECT_FIELDS, MEDICATION_DETAILS, INTERACTION_OUTPUT_DATE_FORMAT, CM_APP_MEDICATIONS_MODULE, PD2AM, PD2BPM, PD2CHM, PD2DIABM, PD2DEPM, PD2SCM, PD2OM, CM_APP_APPOINTMENTS_MODULE, AP2, PM_PM2
from custom.succeed.reports import PD1, PD2, PM3, PM4, HUD2, CM6, CHW3
from custom.succeed.reports.patient_Info import PatientInfoDisplay
from custom.succeed.utils import format_date, SUCCEED_CM_APPNAME, is_pm_or_pi, is_cm, is_pi, SUCCEED_PM_APPNAME, SUCCEED_CHW_APPNAME, is_chw, SUCCEED_DOMAIN, get_app_build
from dimagi.utils.decorators.memoized import memoized


class PatientInfoReport(CustomProjectReport, DrilldownReportMixin, ElasticProjectInspectionReport, ProjectReportParametersMixin):
    slug = "patient"

    hide_filters = True
    filters = []
    ajax_pagination = True
    asynchronous = True
    emailable = False
    xform_es = ReportXFormES(SUCCEED_DOMAIN)

    default_sort = {
        "received_on": "desc"
    }

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        self.view_mode = request.GET.get('view', 'info')
        super(PatientInfoReport, self).__init__(request, base_context, domain, **kwargs)

    @property
    def fields(self):
        if self.view_mode == 'submissions' and self.submission_user_access:
            return ['custom.succeed.fields.PatientFormNameFilter',
                    'corehq.apps.reports.standard.cases.filters.CaseSearchFilter']
        else:
            return []

    @property
    def base_template_filters(self):
        if self.view_mode == 'submissions' and self.submission_user_access:
            return 'succeed/report.html'
        else:
            return super(PatientInfoReport, self).base_template_filters

    @property
    def name(self):
        if self.view_mode == 'submissions':
            return "Patient Submissions"
        if self.view_mode == 'status':
            return 'Manage Patient Status'
        if self.view_mode == 'interactions':
            return 'Manage Patient Interactions'

        return "Patient Info"

    def get_case(self):
        if self.request.GET.get('patient_id', None) is None:
            return None
        return CommCareCase.get(self.request.GET['patient_id'])

    @property
    def submission_user_access(self):
        user = self.request.couch_user
        if user and (is_pi(user) or is_cm(user) or is_chw(user)):
            return True
        return False

    @property
    def patient_status_access(self):
        user = self.request.couch_user
        if user and is_pm_or_pi(user):
            return True
        return False

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
            self.report_template_path = "patient_error.html"
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
                form_idx = None

            return html.escape(get_cloudcare_form_url(domain=self.domain,
                                                      app_build_id=app_build_id,
                                                      module_id=module_idx,
                                                      form_id=form_idx,
                                                      case_id=case_id) + '/enter/')

        try:
            cm_app_dict = get_cloudcare_app(case['domain'], SUCCEED_CM_APPNAME)
            latest_cm_build = get_app_build(cm_app_dict)
            pm_app_dict = get_cloudcare_app(case['domain'], SUCCEED_PM_APPNAME)
            latest_pm_build = get_app_build(pm_app_dict)
            chw_app_dict = get_cloudcare_app(case['domain'], SUCCEED_CHW_APPNAME)
            latest_chw_build = get_app_build(pm_app_dict)
        except ResourceNotFound as ex:
            self.report_template_path = "patient_error.html"
            ret['error_message'] = ex.message
            return ret

        ret['patient'] = case
        ret['root_url'] = '?patient_id=%s' % case['_id']
        ret['view_mode'] = self.view_mode
        ret['patient_status_access'] = self.patient_status_access
        ret['submission_user_access'] = self.submission_user_access

        if self.view_mode == 'info':
            self.report_template_path = "patient_info.html"
            patient_info = PatientInfoDisplay(case)

            #  check user role:
            user = self.request.couch_user
            if is_pm_or_pi(user):
                ret['edit_patient_info_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM_PM2, case['_id'])
            elif is_cm(user):
                ret['edit_patient_info_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PM2, case['_id'])
            elif is_chw(user):
                ret['edit_patient_info_url'] = get_form_url(chw_app_dict, latest_chw_build, CHW_APP_PD_MODULE, PM2, case['_id'])

            if is_pm_or_pi(user):
                ret['upcoming_appointments_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM_PM2, case['_id'])
            elif is_cm(user):
                ret['upcoming_appointments_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PM2, case['_id'])
            elif is_chw(user):
                ret['upcoming_appointments_url'] = get_form_url(chw_app_dict, latest_chw_build, CHW_APP_MA_MODULE, AP2, case['_id'])

            ret['general_information'] = patient_info.general_information
            ret['contact_information'] = patient_info.contact_information
            ret['most_recent_lab_exams'] = patient_info.most_recent_lab_exams
            ret['allergies'] = patient_info.allergies

        elif self.view_mode == 'submissions':
            if self.submission_user_access:
                tabular_context = super(PatientInfoReport, self).report_context
                tabular_context.update(ret)
                self.report_template_path = "patient_submissions.html"
                tabular_context['patient_id'] = self.request_params['patient_id']

                return tabular_context
            else:
                self.report_template_path = "patient_error.html"
                ret['error_message'] = "Cannot access report(incorrect user role)"
                return ret
        elif self.view_mode == 'interactions':
            self.report_template_path = "patient_interactions.html"
            ret['problem_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_PD_MODULE, PD1, case['_id'])
            ret['huddle_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_HUD_MODULE, HUD2, case['_id'])
            ret['cm_phone_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_CM_MODULE, CM6, case['_id'])
            ret['chw_phone_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_CHW_MODULE, CHW3, case['_id'])
            ret['cm_visits_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_APPOINTMENTS_MODULE, AP2, case['_id'])

            ret['anti_thrombotic_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2AM, case['_id'])
            ret['blood_pressure_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2BPM, case['_id'])
            ret['cholesterol_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2CHM, case['_id'])
            ret['depression_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2DIABM, case['_id'])
            ret['diabetes_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2DEPM, case['_id'])
            ret['smoking_cessation_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2SCM, case['_id'])
            ret['other_meds_url'] = get_form_url(cm_app_dict, latest_cm_build, CM_APP_MEDICATIONS_MODULE, PD2OM, case['_id'])

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
                        interaction['received_date'] = action['date'].strftime(INTERACTION_OUTPUT_DATE_FORMAT)
                        try:
                            user = CouchUser.get(action['user_id'])
                            interaction['completed_by'] = user.raw_username
                        except ResourceNotFound:
                            interaction['completed_by'] = EMPTY_FIELD
                        del case['actions'][key]
                        break
                if visit['show_button']:
                    interaction['url'] = get_form_url(cm_app_dict, latest_cm_build, visit['module_idx'], visit['xmlns'], case['_id'])
                if 'scheduled_source' in visit and case.get_case_property(visit['scheduled_source']):
                    interaction['scheduled_date'] = format_date(case.get_case_property(visit['scheduled_source']), INTERACTION_OUTPUT_DATE_FORMAT)

                ret['interaction_table'].append(interaction)

                medication = []
                for med_prop in MEDICATION_DETAILS:
                    medication.append(getattr(case, med_prop, EMPTY_FIELD))
                ret['medication_table'] = medication

        elif self.view_mode == 'plan':
            self.report_template_path = "patient_plan.html"
        elif self.view_mode == 'status':
            if self.patient_status_access:
                self.report_template_path = "patient_status.html"
                ret['disenroll_patient_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM3)
                ret['change_patient_data_url'] = get_form_url(pm_app_dict, latest_pm_build, PM_APP_PM_MODULE, PM4)
            else:
                self.report_template_path = "patient_error.html"
                ret['error_message'] = "Only PMs can disenrollment participants"
                return ret
        else:
            raise Http404
        return ret

    def submit_history_form_link(self, form_id, form_name):
        url = reverse('render_form_data', args=[self.domain, form_id])
        return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, html.escape(form_name)))

    @memoized
    def form_submitted_by(self, user_id):
        try:
            user = CommCareUser.get(user_id)
            return user.human_friendly_name
        except ResourceNotFound:
            return "%s (User Not Found)" % user_id

    def form_completion_time(self, date_string):
        if date_string != EMPTY_FIELD:
            date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
            return date.strftime("%m/%d/%Y %H:%M")
        else:
            return EMPTY_FIELD

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Form Name", sortable=False, span=1),
            DataTablesColumn("Submitted By", sortable=False, span=1),
            DataTablesColumn("Completed", sortable=False, span=1)
        )

    @property
    def es_results(self):
        if not self.request.GET.has_key('patient_id'):
            return None

        full_query = {
            'query': {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": self.request.domain}},
                            {"term": {"doc_type": "xforminstance"}},
                            {
                                "nested": {
                                    "path": "form.case",
                                    "filter": {
                                        "or": [
                                            {
                                                "term": {
                                                    "@case_id": "%s" % self.request.GET[
                                                        'patient_id']
                                                }
                                            },
                                            {
                                                "term": {
                                                    "case_id": "%s" % self.request.GET['patient_id']
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "sort": self.get_sorting_block(),
            "size": self.pagination.count,
            "from": self.pagination.start
        }

        form_name_group = self.request.GET.get('form_name_group', None)
        form_name_xmnls = self.request.GET.get('form_name_xmlns', None)
        search_string = SearchFilter.get_value(self.request, self.domain)

        if search_string:
            query_block = {"queryString": {"query": "*" + search_string + "*"}}
            full_query["query"]["filtered"]["query"] = query_block

        if form_name_group and form_name_xmnls == '':
            xmlns_terms = []
            forms = filter(lambda obj: obj['val'] == form_name_group, SUBMISSION_SELECT_FIELDS)[0]
            for form in forms['next']:
                xmlns_terms.append(form['val'])

            full_query['query']['filtered']['filter']['and'].append({"terms": {"xmlns.exact": xmlns_terms}})

        if form_name_xmnls:
            full_query['query']['filtered']['filter']['and'].append({"term": {"xmlns.exact": form_name_xmnls}})

        res = self.xform_es.run_query(full_query)
        return res

    @property
    def rows(self):
        if self.request.GET.has_key('patient_id'):
            def _format_row(row_field_dict):
                return [self.submit_history_form_link(row_field_dict["_id"],
                                                      row_field_dict['_source'].get('es_readable_name', EMPTY_FIELD)),
                        self.form_submitted_by(row_field_dict['_source']['form']['meta'].get('userID', EMPTY_FIELD)),
                        self.form_completion_time(row_field_dict['_source']['form']['meta'].get('timeEnd', EMPTY_FIELD))
                ]

            res = self.es_results
            if res:
                if res.has_key('error'):
                    pass
                else:
                    for result in res['hits']['hits']:
                        yield list(_format_row(result))

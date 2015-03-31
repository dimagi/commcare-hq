from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from django.utils import html
from dimagi.utils.decorators.memoized import memoized
from custom.succeed.utils import get_app_build, SUCCEED_CM_APPNAME, SUCCEED_PM_APPNAME, SUCCEED_CHW_APPNAME, \
    SUCCEED_DOMAIN
from casexml.apps.case.models import CommCareCase

EMPTY_URL = ''


class PatientDetailsReport(CustomProjectReport, ElasticProjectInspectionReport, ProjectReportParametersMixin):
    name = 'Patient Details'
    slug = 'patient'
    report_template_path = ""

    hide_filters = True
    filters = []
    flush_layout = True
    fields = []
    es_results=None

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if domain and project and user is None:
            return True
        return False

    @property
    @memoized
    def case(self):
        if self.request.GET.get('patient_id', None) is None:
            return None
        return CommCareCase.get(self.request.GET['patient_id'])

    def get_form_url(self, app_dict, app_build_id, module_idx, form, case_id=None, parent_id=None):
        try:
            module = app_dict['modules'][module_idx]
            if len(module['forms']) == 1:
                form_idx = 0
            else:
                form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == form][0]
        except IndexError:
            form_idx = None

        if case_id is None and parent_id is not None:
            url = get_cloudcare_form_url(domain=self.domain,
                                         app_build_id=app_build_id,
                                         module_id=module_idx,
                                         form_id=form_idx,
                                         case_id=case_id) + '/parent/' + parent_id
        else:
            url = get_cloudcare_form_url(domain=self.domain,
                                         app_build_id=app_build_id,
                                         module_id=module_idx,
                                         form_id=form_idx,
                                         case_id=case_id) + '/enter/'
        return html.escape(url)

    def update_app_info(self):
        self.cm_app_dict = get_cloudcare_app(SUCCEED_DOMAIN, SUCCEED_CM_APPNAME)
        self.latest_cm_build = get_app_build(self.cm_app_dict)
        self.pm_app_dict = get_cloudcare_app(SUCCEED_DOMAIN, SUCCEED_PM_APPNAME)
        self.latest_pm_build = get_app_build(self.pm_app_dict)
        self.chw_app_dict = get_cloudcare_app(SUCCEED_DOMAIN, SUCCEED_CHW_APPNAME)
        self.latest_chw_build = get_app_build(self.chw_app_dict)

    @property
    def report_context(self):
        ret = {}
        try:
            ret['patient'] = self.case
        except ResourceNotFound:
            self.report_template_path = "patient_error.html"
            ret['error_message'] = "Patient not found"
            return ret
        ret['patient_info_url'] = self.patient_info_url
        ret['patient_submission_url'] = self.patient_submission_url
        ret['patient_interactions_url'] = self.patient_interactions_url
        ret['patient_status_url'] = self.patient_status_url
        return ret

    @property
    @memoized
    def is_all_reports_enabled(self):
        return self.request.couch_user.get_role().permissions.view_reports

    @property
    @memoized
    def get_available_report_list(self):
        return self.request.couch_user.get_role().permissions.view_report_list

    def get_class_path(self, report_class):
        return unicode(report_class.__module__+'.'+report_class.__name__)

    @property
    def patient_info_url(self):
        from custom.succeed.reports.patient_Info import PatientInfoReport
        if self.is_all_reports_enabled or self.get_class_path(PatientInfoReport) in self.get_available_report_list:
            return html.escape(
                PatientInfoReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case['_id'])
        return EMPTY_URL

    @property
    def patient_submission_url(self):
        from custom.succeed.reports.patient_submissions import PatientSubmissionReport
        if self.is_all_reports_enabled or self.get_class_path(PatientSubmissionReport) in self.get_available_report_list:
            return html.escape(
                PatientSubmissionReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case['_id'])
        else:
            return EMPTY_URL

    @property
    def patient_interactions_url(self):
        from custom.succeed.reports.patient_interactions import PatientInteractionsReport
        if self.is_all_reports_enabled or self.get_class_path(PatientInteractionsReport) in self.get_available_report_list:
            return html.escape(
                PatientInteractionsReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case['_id'])
        else:
            return EMPTY_URL

    @property
    def patient_status_url(self):
        from custom.succeed.reports.patient_status import PatientStatusReport
        if self.is_all_reports_enabled or self.get_class_path(PatientStatusReport) in self.get_available_report_list:
            return html.escape(
                PatientStatusReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case['_id'])
        else:
            return EMPTY_URL

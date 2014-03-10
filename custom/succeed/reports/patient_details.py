from django.http.response import Http404
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import CustomProjectReport
from casexml.apps.case.models import CommCareCase
from custom.succeed.reports import DrilldownReportMixin


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
        except Exception:
            has_error = True
            case = None

        if case is None:
            self.report_template_path = "nopatient.html"
            if has_error:
                ret['error_message'] = "Patient not found"
            else:
                ret['error_message'] = "No patient selected"
            return ret

        view_mode = self.request.GET.get('view', 'info')
        ret['patient'] = case
        ret['root_url'] = '?patient_id=%s' % case['_id']
        ret['view_mode'] = view_mode

        if view_mode == 'info':
            self.report_template_path = "patient_info.html"
        elif view_mode == 'submissions':
            self.report_template_path = "patient_submissions.html"
        elif view_mode == 'interactions':
            self.report_template_path = "patient_interactions.html"
        elif view_mode == 'plan':
            self.report_template_path = "patient_plan.html"
        elif view_mode == 'status':
            self.report_template_path = "patient_status.html"
        else:
            raise Http404
        return ret

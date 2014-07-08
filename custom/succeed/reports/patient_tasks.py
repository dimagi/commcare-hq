from django.utils import html
from custom.succeed.reports.patient_task_list import PatientTaskListReport
from custom.succeed.reports import CM_APP_UPDATE_VIEW_TASK_MODULE, CHW_APP_TASK_MODULE, CM_NEW_TASK

from custom.succeed.reports.patient_details import PatientDetailsReport
from custom.succeed.utils import is_cm, is_chw


class PatientTasksReport(PatientDetailsReport):
    slug = "patient_tasks"
    name = 'Patient Tasks'

    @property
    def report_context(self):
        self.report_template_path = "patient_tasks.html"
        ret = super(PatientTasksReport, self).report_context
        ret['view_mode'] = 'plan'
        case = self.get_case()

        #  check user role:
        user = self.request.couch_user
        ret['patient_task_list_url'] = html.escape(PatientTaskListReport.get_url(*[case["domain"]]) + "?patient_id=%s&task_status=%s" % (case["_id"], "open"))
        if is_cm(user):
            ret['create_new_task_url'] = self.get_form_url(self.cm_app_dict, self.latest_cm_build, CM_APP_UPDATE_VIEW_TASK_MODULE, CM_NEW_TASK)
        elif is_chw(user):
            ret['create_new_task_url'] = self.get_form_url(self.chw_app_dict, self.latest_chw_build, CHW_APP_TASK_MODULE, CM_NEW_TASK)
        return ret
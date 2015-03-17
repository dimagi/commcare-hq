from django.utils import html
from custom.succeed.reports.patient_task_list import PatientTaskListReport
from custom.succeed.reports import CHW_APP_TASK_MODULE, CM_NEW_TASK, CM_APP_CREATE_TASK_MODULE

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

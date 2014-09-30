from django.utils.translation import ugettext_noop as _
from custom.succeed.reports.all_patients import PatientListReport
from custom.succeed.reports.patient_Info import PatientInfoReport
from custom.succeed.reports.patient_tasks import PatientTasksReport
from custom.succeed.reports.patient_interactions import PatientInteractionsReport
from custom.succeed.reports.patient_status import PatientStatusReport
from custom.succeed.reports.patient_submissions import PatientSubmissionReport
from custom.succeed.reports.patient_task_list import PatientTaskListReport


CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       PatientListReport,
       PatientTaskListReport,
       PatientInfoReport,
       PatientSubmissionReport,
       PatientInteractionsReport,
       PatientTasksReport,
       PatientStatusReport
    )),
)
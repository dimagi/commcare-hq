from django.utils.translation import ugettext_noop as _
from custom.succeed.reports.all_patients import PatientListReport
from custom.succeed.reports.patient_Info import PatientInfoReport
from custom.succeed.reports.patient_careplan import PatientCarePlanReport
from custom.succeed.reports.patient_interactions import PatientInteractionsReport
from custom.succeed.reports.patient_status import PatientStatusReport
from custom.succeed.reports.patient_submissions import PatientSubmissionReport


CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       PatientListReport,
       PatientInfoReport,
       PatientSubmissionReport,
       PatientInteractionsReport,
       PatientCarePlanReport,
       PatientStatusReport
    )),
)
from django.utils.translation import ugettext_noop as _
from custom.succeed.reports.all_patients import PatientListReport
from custom.succeed.reports.patient_details import PatientInfoReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       PatientListReport,
       PatientInfoReport,
    )),
)
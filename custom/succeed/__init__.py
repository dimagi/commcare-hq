from django.utils.translation import ugettext_noop as _
from custom.succeed.reports.all_patients import PatientListReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       PatientListReport,
    )),
)
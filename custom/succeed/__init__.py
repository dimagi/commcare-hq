from django.utils.translation import ugettext_noop as _
from custom.succeed.reports import PatientListReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       PatientListReport,
    )),
)
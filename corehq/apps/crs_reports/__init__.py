from corehq.apps.crs_reports.reports import HNBCMotherReport, HNBCInfantReport
from django.utils.translation import ugettext_noop as _

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HNBCMotherReport,
       HNBCInfantReport,
    )),
)


from django.utils.translation import ugettext_noop as _

from custom.apps.crs_reports.reports import HNBCMotherReport, HNBCInfantReport


CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HNBCMotherReport,
       HNBCInfantReport,
    )),
)


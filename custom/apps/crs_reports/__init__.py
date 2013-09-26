from django.utils.translation import ugettext_noop as _

from custom.apps.crs_reports.reports import HBNCMotherReport, HBNCInfantReport


CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HBNCMotherReport,
       HBNCInfantReport,
    )),
)


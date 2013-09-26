from django.utils.translation import ugettext_noop as _
from django.conf.urls.defaults import *
from corehq.apps.reports.urls import custom_report_urls

from custom.apps.crs_reports.reports import HBNCMotherReport, HBNCInfantReport

custom_report_urls += patterns('',
    (r"^crs-report/", include("custom.apps.crs_reports.urls")),
)

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
       HBNCMotherReport,
       HBNCInfantReport,
    )),
)
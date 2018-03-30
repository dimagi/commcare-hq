# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.reports.dashboard_1 import Dashboard1Report
from custom.yeksi_naa_reports.reports.dashboard_2 import Dashboard2Report
from custom.yeksi_naa_reports.reports.dashboard_3 import Dashboard3Report

CUSTOM_REPORTS = (
    ("Yeksi Naa Reports", (
        Dashboard1Report,
        Dashboard2Report,
        Dashboard3Report,
    )),
)

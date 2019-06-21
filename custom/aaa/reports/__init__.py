from __future__ import absolute_import
from __future__ import unicode_literals

from custom.aaa.reports.reports import DashboardReport

CUSTOM_REPORTS = (
    ('CUSTOM REPORTS', (
        DashboardReport,
    )),
)

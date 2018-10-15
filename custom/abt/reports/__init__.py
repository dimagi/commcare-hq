from __future__ import absolute_import
from __future__ import unicode_literals

from custom.abt.reports.late_pmt import LatePmtReport

CUSTOM_REPORTS = (
    ('CUSTOM REPORTS', (
        LatePmtReport,
    )),
)

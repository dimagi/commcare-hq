from custom.abt.reports.late_pmt import LatePmtReport
from custom.abt.reports.late_pmt_2020 import LatePmt2020Report

CUSTOM_REPORTS = (
    ('CUSTOM REPORTS', (
        LatePmtReport,
        LatePmt2020Report,
    )),
)

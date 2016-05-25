from custom.icds_reports.reports.reports import MPRReport, ASRReport

CUSTOM_REPORTS = (
    ('BLOCK REPORTS', (
        MPRReport,
        ASRReport
    )),
)

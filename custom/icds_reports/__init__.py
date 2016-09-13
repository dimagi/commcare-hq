from custom.icds_reports.reports.reports import MPRReport, ASRReport, TableauReport

CUSTOM_REPORTS = (
    ('BLOCK REPORTS', (
        MPRReport,
        ASRReport
    )),
    ('CUSTOM REPORTS', (
        TableauReport,
    )),
)

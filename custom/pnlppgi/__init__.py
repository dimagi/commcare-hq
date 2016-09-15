from custom.pnlppgi.reports import SiteReportingRatesReport, WeeklyMalaria

CUSTOM_REPORTS = (
    ('Custom Reports', (
        SiteReportingRatesReport,
        WeeklyMalaria
    )),
)

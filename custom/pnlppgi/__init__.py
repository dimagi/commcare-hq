from custom.pnlppgi.reports import SiteReportingRatesReport, WeeklyMalaria, CumulativeMalaria

CUSTOM_REPORTS = (
    ['Custom Reports', (
        SiteReportingRatesReport,
        WeeklyMalaria,
        CumulativeMalaria
    )],
)

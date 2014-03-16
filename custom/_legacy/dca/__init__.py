from dca.reports import (ProjectOfficerReport, PortfolioComparisonReport,
        PerformanceReport, PerformanceRatiosReport)

CUSTOM_REPORTS = (
    ('Custom Reports', (
        ProjectOfficerReport,
        PortfolioComparisonReport,
        PerformanceReport,
        PerformanceRatiosReport
    )),
)

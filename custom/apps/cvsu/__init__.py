from .reports import ChildProtectionReport, ChildProtectionReportTrend, CVSUPerformanceReport, \
    CVSUPerformanceReportTrend

CUSTOM_REPORTS = (
    ('Child Protection & Gender based Violence', (
        ChildProtectionReport,
        ChildProtectionReportTrend,
    )),
    ('Performance Evaluation', (
        CVSUPerformanceReport,
        CVSUPerformanceReportTrend,
    ))
)

from custom.apps.cvsu.new_reports import NewChildProtectionReport, NewCVSUPerformanceReport, \
    NewCVSUPerformanceReportTrend, NewChildProtectionReportTrend
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
    )),
    ('New Child Protection & Gender based Violence', (
        NewChildProtectionReport,
        NewChildProtectionReportTrend,
    )),
    ('New Performance Evaluation', (
        NewCVSUPerformanceReport,
        NewCVSUPerformanceReportTrend,
    )),
)

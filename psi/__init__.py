from psi.reports import (PSIEventsReport, PSIHDReport, PSISSReport, PSITSReport)
from psi.reports.sql_reports import PSISQLEventsReport, PSISQLSensitizationReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        # PSIEventsReport,
        PSISQLEventsReport,
        PSIHDReport,
        PSISQLSensitizationReport,
        PSITSReport,
    )),

)

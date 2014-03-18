from psi.reports import (PSIEventsReport, PSIHDReport, PSISSReport, PSITSReport)
from psi.reports.sql_reports import PSISQLEventsReport, PSISQLHouseholdReport, PSISQLSensitizationReport, PSISQLTrainingReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        PSIEventsReport,
        PSIHDReport,
        PSISSReport,
        PSITSReport,
        PSISQLEventsReport,
        PSISQLHouseholdReport,
        PSISQLSensitizationReport,
        PSISQLTrainingReport,
    )),

)

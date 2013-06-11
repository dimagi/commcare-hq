from psi.reports import (PSIEventsReport, PSIHDReport, PSISSReport, PSISQLEventsReport,
    PSITSReport)

CUSTOM_REPORTS = (
    ('Custom Reports', (
        PSIEventsReport,
        PSISQLEventsReport,
        PSIHDReport,
        PSISSReport,
        PSITSReport,
    )),

)

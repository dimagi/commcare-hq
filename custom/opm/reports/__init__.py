# from psi.reports import (PSIEventsReport, PSIHDReport, PSISSReport, PSITSReport)
# from psi.reports.sql_reports import PSISQLEventsReport
from . import reports

CUSTOM_REPORTS = (
    ('Custom Reports', (
        reports.BeneficiaryPaymentReport,
        reports.IncentivePaymentReport,
    )),

)

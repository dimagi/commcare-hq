from custom.trialconnect.reports.appointments import AppointmentsReport
from custom.trialconnect.reports.system_overview import SystemOverviewReport, SystemUsersReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        SystemOverviewReport,
        SystemUsersReport,
        AppointmentsReport,
    )),
)

from custom.fri.reports.reports import MessageBankReport, MessageReport, PHEDashboardReport

CUSTOM_REPORTS = (
    ('FRI', (
        PHEDashboardReport,
        MessageBankReport,
        MessageReport,
    )),
)

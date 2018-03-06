from __future__ import absolute_import
from __future__ import unicode_literals
from custom.fri.reports.reports import (
    MessageBankReport, MessageReport, PHEDashboardReport,
    SurveyResponsesReport,
)

CUSTOM_REPORTS = (
    ('FRI', (
        PHEDashboardReport,
        SurveyResponsesReport,
        MessageBankReport,
        MessageReport,
    )),
)

from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop as _

from custom.bihar.reports import supervisor, mch_reports
from custom.bihar.reports.indicators import reports as indicators

# some static strings go here

_("Active Cases")
_("Total Cases")
_("Total Form Submissions")
_("Days Since Last Submission")
_("Clients Visited")
_("Inactive Clients")

CUSTOM_REPORTS = (
    ('Custom Reports', (
        supervisor.MainNavReport,
        supervisor.ToolsNavReport,
        supervisor.ReferralListReport,
        supervisor.EDDCalcReport,
        supervisor.BMICalcReport,
        supervisor.SubCenterSelectionReport,
        indicators.IndicatorNav,
        indicators.IndicatorSummaryReport,
        indicators.IndicatorClientSelectNav,
        indicators.IndicatorClientList,
        indicators.IndicatorCharts,
        indicators.MyPerformanceReport,
        indicators.MyPerformanceList,
        mch_reports.MotherMCHRegister,
        mch_reports.ChildMCHRegister
    )),
)

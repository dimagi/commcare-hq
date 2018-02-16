from __future__ import absolute_import
from django.utils.translation import ugettext_noop as _

from custom.bihar.reports import supervisor, due_list, mch_reports
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
        due_list.DueListSelectionReport,
        due_list.DueListNav,
        due_list.VaccinationSummary,
        due_list.VaccinationSummaryToday,
        due_list.VaccinationSummaryTomorrow,
        due_list.VaccinationSummary2Days,
        due_list.VaccinationSummary3Days,
        due_list.VaccinationClientList,
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

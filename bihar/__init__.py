from bihar.reports import supervisor
from bihar.reports.indicators import reports as indicators

CUSTOM_REPORTS = (
    ('Custom Reports', (
        supervisor.MainNavReport,
        supervisor.WorkerRankSelectionReport,
        supervisor.DueListReport,
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
    )),
)

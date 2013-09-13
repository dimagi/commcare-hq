from bihar.reports import supervisor, due_list
from bihar.reports.indicators import reports as indicators

CUSTOM_REPORTS = (
    ('Custom Reports', (
        supervisor.MainNavReport,
        supervisor.WorkerRankSelectionReport,
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
    )),
)

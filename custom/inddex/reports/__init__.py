from custom.inddex.reports.gaps_report_by_item import GapsReportByItem
from custom.inddex.reports.master_data_file import MasterDataFileSummaryReport
from custom.inddex.reports.nutrient_intakes import NutrientIntakesReport
from custom.inddex.reports.summary_statistics_report import SummaryStatisticsReport
from custom.inddex.reports.gaps_summary_by_food_type import GapsSummaryByFoodTypeSummaryReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        MasterDataFileSummaryReport,
        GapsSummaryByFoodTypeSummaryReport,
        GapsReportByItem,
        NutrientIntakesReport,
        SummaryStatisticsReport
    )),
)

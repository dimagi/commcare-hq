from custom.inddex.reports.gaps_summary import GapsSummaryReport
from custom.inddex.reports.master_data import MasterDataReport
from custom.inddex.reports.gaps_detail import GapsDetailReport
from custom.inddex.reports.nutrient_intake import NutrientIntakeReport
from custom.inddex.reports.nutrient_stats import NutrientStatsReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        MasterDataReport,
        GapsSummaryReport,
        GapsDetailReport,
        NutrientIntakeReport,
        NutrientStatsReport
    )),
)

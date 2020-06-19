from custom.inddex.reports.r1_master_data import MasterDataReport
from custom.inddex.reports.r2a_gaps_summary import GapsSummaryReport
from custom.inddex.reports.r2b_gaps_detail import GapsDetailReport
from custom.inddex.reports.r3_nutrient_intake import NutrientIntakeReport
from custom.inddex.reports.r4_nutrient_stats import NutrientStatsReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        MasterDataReport,
        GapsSummaryReport,
        GapsDetailReport,
        NutrientIntakeReport,
        NutrientStatsReport
    )),
)

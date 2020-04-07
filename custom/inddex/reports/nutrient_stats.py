from memoized import memoized

from custom.inddex.filters import (
    AgeRangeFilter,
    BreastFeedingFilter,
    GenderFilter,
    PregnancyFilter,
    RecallStatusFilter,
    SettlementAreaFilter,
    SupplementsFilter,
)
from custom.inddex.ucr.data_providers.summary_statistics_data import (
    SummaryStatsNutrientDataProvider,
)
from custom.inddex.utils import MultiTabularReport


class NutrientStatsReport(MultiTabularReport):
    title = 'Output 4 - Nutrient Intake Summary Statistics'
    name = title
    slug = 'nutrient_stats'

    @property
    def fields(self):
        return super().fields + [
            GenderFilter,
            AgeRangeFilter,
            PregnancyFilter,
            BreastFeedingFilter,
            SettlementAreaFilter,
            SupplementsFilter,
            RecallStatusFilter
        ]

    @property
    def report_config(self):
        report_config = {}  # TODO port to FoodData.from_request
        request_slugs = [
            'gender',
            'age_range',
            'pregnant',
            'breastfeeding',
            'urban_rural',
            'supplements',
            'recall_status',
        ]
        report_config.update({slug: self.request.GET.get(slug, '')
                              for slug in request_slugs})
        return report_config

    @property
    @memoized
    def data_providers(self):
        return [
            SummaryStatsNutrientDataProvider(config=self.report_config)
        ]

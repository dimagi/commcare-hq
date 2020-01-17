from custom.inddex.filters import GapTypeFilter, GapDescriptionFilter, FoodTypeFilter, FoodCodeFilter, \
    RecallStatusFilter
from custom.inddex.utils import MultiTabularReport


class GapsReportByItemBase(MultiTabularReport):

    @property
    def fields(self):
        fields = super(GapsReportByItemBase, self).fields
        fields += [
            GapTypeFilter,
            GapDescriptionFilter,
            FoodTypeFilter,
            FoodCodeFilter,
            RecallStatusFilter
        ]

        return fields

    @property
    def report_config(self):
        report_config = super(GapsReportByItemBase, self).report_config
        report_config.update(
            gap_type=self.gap_type,
            gap_description=self.gap_description,
            food_code=self.food_code,
            food_type=self.food_type,
            recall_status=self.recall_status
        )

        return report_config

    @property
    def gap_type(self):
        return self.request.GET.get('gap_type') or ''

    @property
    def gap_description(self):
        return self.request.GET.get('gap_description') or ''

    @property
    def food_code(self):
        return self.request.GET.get('food_code') or ''

    @property
    def food_type(self):
        return self.request.GET.get('food_type') or ''

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''

    @property
    def rows(self):
        return super(GapsReportByItemBase, self).rows

    @property
    def headers(self):
        return super(GapsReportByItemBase, self).headers

    @property
    def data_providers(self):
        return super(GapsReportByItemBase, self).data_providers

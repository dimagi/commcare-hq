from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.inddex.sqldata import FoodConsumptionDataSourceMixin
from sqlagg.filters import EQ


class SummaryStatsNutrientDataProvider(FoodConsumptionDataSourceMixin):
    total_row = None
    title = 'Group-level Summary Statistics by Nutrient Intake'
    slug = 'group_level_summary_statistics_by_nutrient_intake'

    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config

    @property
    def headers(self):
        return DataTablesHeader(
                DataTablesColumn('Nutrient'),
                DataTablesColumn('Mean'),
                DataTablesColumn('Median'),
                DataTablesColumn('Std.Dev'),
                DataTablesColumn('5_percent'),
                DataTablesColumn('25_percent'),
                DataTablesColumn('50_percent'),
                DataTablesColumn('75_percent'),
                DataTablesColumn('95_percent')
        )

    @property
    def filters(self):
        filters = []
        if self.filters_config['gender']:
            filters.append(EQ('gender', 'gender'))
        if self.filters_config['pregnant']:
            filters.append(EQ('pregnant', 'pregnant'))
        if self.filters_config['breastfeeding']:
            filters.append(EQ('breastfeeding', 'breastfeeding'))
        if self.filters_config['urban_rural']:
            filters.append(EQ('urban_rural', 'urban_rural'))
        if self.filters_config['supplements']:
            filters.append(EQ('supplements', 'supplements'))
        if self.filters_config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))
        return filters

    @property
    def filter_values(self):
        return self.filters_config

    @property
    def rows(self):
        # TODO: calculate methods
        return [['resp a', 2, 'n', 'm', 'm', 'std', 5, 25, 50, 75, 95]]

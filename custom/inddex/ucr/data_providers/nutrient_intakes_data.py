from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ

from custom.inddex.sqldata import FoodConsumptionDataSourceMixin


class NutrientIntakesByFoodData(FoodConsumptionDataSourceMixin):
    title = 'Nutrient Intakes By Food'
    slug = 'nutrient_intake_by_food_data'

    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config

    @property
    def columns(self):
        return [
            DatabaseColumn('unique_respondent_id', SimpleColumn('unique_respondent_id')),
            DatabaseColumn('recall_case_id', SimpleColumn('recall_case_id')),
            DatabaseColumn('opened_by_username', SimpleColumn('opened_by_username')),
            DatabaseColumn('owner_name', SimpleColumn('owner_name')),
            DatabaseColumn('recall_date', SimpleColumn('recall_date')),
            DatabaseColumn('recall_status', SimpleColumn('recall_status')),
            DatabaseColumn('gender', SimpleColumn('gender')),
            DatabaseColumn('age', SimpleColumn('age')),
            DatabaseColumn('supplements', SimpleColumn('supplements')),
            DatabaseColumn('urban_rural', SimpleColumn('urban_rural')),
            DatabaseColumn('pregnant', SimpleColumn('pregnant')),
            DatabaseColumn('breastfeeding', SimpleColumn('breastfeeding')),
            DatabaseColumn('food_code', SimpleColumn('food_code')),
            DatabaseColumn('reference_food_code', SimpleColumn('reference_food_code')),
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('food_name', SimpleColumn('food_name')),
            DatabaseColumn('recipe_name', SimpleColumn('recipe_name')),
            DatabaseColumn('food_type', SimpleColumn('food_type')),
            DatabaseColumn('include_in_analysis', SimpleColumn('include_in_analysis')),
            DatabaseColumn('is_ingredient', SimpleColumn('is_ingredient')),
            DatabaseColumn('food_status', SimpleColumn('food_status'))
        ]

    @property
    def headers(self):
        group_columns = tuple(self.group_by)
        headers = []
        for col in group_columns:
            headers.append(DataTablesColumn(col))
        return headers

    @property
    def group_by(self):
        return ['unique_respondent_id', 'recall_case_id', 'opened_by_username', 'owner_name', 'recall_date',
                'recall_status', 'gender', 'age', 'supplements', 'urban_rural', 'pregnant', 'breastfeeding',
                'food_code', 'reference_food_code', 'doc_id', 'food_name', 'recipe_name', 'food_type',
                'include_in_analysis', 'is_ingredient', 'food_status']

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
        result = []
        data_rows = self.get_data()
        group_columns = tuple(self.group_by)

        for row in data_rows:
            result.append([row[x] for x in group_columns])
        return result


class NutrientIntakesByRespondentData(FoodConsumptionDataSourceMixin):
    title = 'Nutrient Intakes By Respondent'
    slug = 'nutrient_intakes_by_respondent'

    def __init__(self, config, filters_config):
        super(NutrientIntakesByRespondentData, self).__init__(config)
        self.filters_config = filters_config

    @property
    def columns(self):
        return [
            DatabaseColumn('unique_respondent_id', SimpleColumn('unique_respondent_id')),
            DatabaseColumn('recall_case_id', SimpleColumn('recall_case_id')),
            DatabaseColumn('opened_by_username', SimpleColumn('opened_by_username')),
            DatabaseColumn('owner_name', SimpleColumn('owner_name')),
            DatabaseColumn('recall_date', SimpleColumn('recall_date')),
            DatabaseColumn('recall_status', SimpleColumn('recall_status')),
            DatabaseColumn('gender', SimpleColumn('gender')),
            DatabaseColumn('age', SimpleColumn('age')),
            DatabaseColumn('supplements', SimpleColumn('supplements')),
            DatabaseColumn('urban_rural', SimpleColumn('urban_rural')),
            DatabaseColumn('pregnant', SimpleColumn('pregnant')),
            DatabaseColumn('breastfeeding', SimpleColumn('breastfeeding')),
            DatabaseColumn('doc_id', SimpleColumn('doc_id'))
        ]

    @property
    def headers(self):
        group_columns = tuple(self.group_by)
        headers = []
        for col in group_columns:
            headers.append(DataTablesColumn(col))
        return headers

    @property
    def group_by(self):
        return ['unique_respondent_id', 'recall_case_id', 'opened_by_username', 'owner_name', 'recall_date',
                'recall_status', 'gender', 'age', 'supplements', 'urban_rural', 'pregnant', 'breastfeeding', 'doc_id']

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
        result = []
        data_rows = self.get_data()
        group_columns = tuple(self.group_by)

        for row in data_rows:
            result.append([row[x] for x in group_columns])
        return result

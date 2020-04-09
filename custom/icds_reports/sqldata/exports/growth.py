from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, RawFilter, ORFilter, LTE
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import get_status, calculate_date_for_age, \
    current_month_stunting_column, \
    current_month_wasting_column, phone_number_function

class GrowthExport(ExportableMixin, IcdsSqlData):
    title = 'Child Growth Tracking'
    table_name = 'child_health_monthly_view'

    def __int__(self, config=None, loc_level=1, show_test=False, beta=False):
        config.update({
            '5_years': 60,
            'true': 1
        })
        super().__init__(config, loc_level, show_test, beta, use_excluded_states=False)

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = []
        for column in group_by_columns:
            if column.slug != 'current_age':
                group_by.append(column.slug)
        return group_by

    def _map_filter_name_to_sql_filter(self, filter_name):
        return {
            'severely_underweight': RawFilter("current_month_nutrition_status = 'severely_underweight'"),
            'moderately_underweight': RawFilter("current_month_nutrition_status = 'moderately_underweight'"),
            'normal_wfa': RawFilter("current_month_nutrition_status = 'normal'"),
            'severely_stunted': RawFilter("{} = 'severe'".format(current_month_stunting_column(self.beta))),
            'moderately_stunted': RawFilter("{} = 'moderate'".format(current_month_stunting_column(self.beta))),
            'normal_hfa': RawFilter("{} = 'normal'".format(current_month_stunting_column(self.beta))),
            'severely_wasted': RawFilter("{} = 'severe'".format(current_month_wasting_column(self.beta))),
            'moderately_wasted': RawFilter("{} = 'moderate'".format(current_month_wasting_column(self.beta))),
            'normal_wfh': RawFilter("{} = 'normal'".format(current_month_wasting_column(self.beta))),
        }[filter_name]

    def _build_additional_filters(self, filters):
        if len(filters) == 1:
            return self._map_filter_name_to_sql_filter(filter[0])
        return ORFilter([
            self._map_filter_name_to_sql_filter(filter_name)
            for filter_name in filters
        ])

    @property
    def filters(self):
        filters = [LTE('age_in_months', '5_years'), EQ('valid_in_month', 'true')]
        for key, value in self.config.items():
            if key in ['domain', '5_years', 'true']
                continue
            elif key == 'filters':
                filters.append(self._build_additional_filters(value))
                continue
            filters.append(EQ(key, key))
        return filters

    @property
    def order_by(self):
        return [OrderBy('person_name')]

    @property
    def get_columns_by_loc_level(self):
        selected_month = self.config['month']

        columns = [
            DatabaseColumn(
                'State',
                SimpleColumn('state_name'),
                slug='state_name'
            ),
            DatabaseColumn(
                'District',
                SimpleColumn('district_name'),
                slug='district_name'
            ),
            DatabaseColumn(
                'Block',
                SimpleColumn('block_name'),
                slug='block_name'
            ),
            DatabaseColumn(
                'Sector',
                SimpleColumn('supervisor_name'),
                slug='supervisor_name'
            ),
            DatabaseColumn(
                'AWC Name',
                SimpleColumn('awc_name'),
                slug='awc_name'
            ),
            DatabaseColumn(
                'AWC Site Code',
                SimpleColumn('awc_site_code'),
                slug='awc_site_code'
            ),
            DatabaseColumn(
                'Child Name',
                SimpleColumn('person_name'),
                slug='person_name'
            ),
            DatabaseColumn(
                'Current Age (as of {})'.format(selected_month.isoformat()),
                AliasColumn('dob'),
                format_fn=lambda x: calculate_date_for_age(x, self.config['month']),
                slug='current_age'
            ),
            DatabaseColumn(
                'Mother name',
                SimpleColumn('mother_name'),
                slug='mother_name'
            ),
            DatabaseColumn(
                'Mother Phone Number',
                SimpleColumn('mother_phone_number'),
                format_fn=phone_number_function,
                slug='mother_phone_number'
            )
            DatabaseColumn(
                'Days attended PSE (as of {})'.format(selected_month.isoformat()),
                SimpleColumn('pse_days_attended'),
                slug="pse_days_attended"
            ),
            DatabaseColumn(
                'Rations Distributed (as of {})'.format(selected_month.isoformat()),
                SimpleColumn('num_rations_distributed'),
                slug="num_rations_distributed"
            ),
            DatabaseColumn(
                'Weight-for-Age Status (in Month)',
                SimpleColumn('current_month_nutrition_status'),
                format_fn=lambda x: get_status(
                    x,
                    'underweight',
                    'Normal weight for age',
                    True
                ),
                slug='current_month_nutrition_status'
            ),
            DatabaseColumn(
                'Weight-for-Height Status (in Month)',
                SimpleColumn(current_month_wasting_column(self.beta)),
                format_fn=lambda x: get_status(
                    x,
                    'wasted',
                    'Normal weight for height',
                    True
                ),
                slug=current_month_wasting_column(self.beta)
            ),
            DatabaseColumn(
                'Height-for-Age status (in Month)',
                SimpleColumn(current_month_stunting_column(self.beta)),
                format_fn=lambda x: get_status(
                    x,
                    'stunted',
                    'Normal height for age',
                    True
                ),
                slug=current_month_stunting_column(self.beta)
            )
        ]
        return columns

    @property
    def columns(self):
        return self.get_columns_by_loc_level

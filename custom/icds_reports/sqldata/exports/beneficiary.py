from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import six
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, RawFilter, ORFilter, LTE
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.icds_reports.sqldata.base import IcdsSqlData, ICDSDatabaseColumn
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import get_status, calculate_date_for_age, \
    current_month_stunting_column, \
    current_month_wasting_column, format_decimal, DATA_NOT_ENTERED, phone_number_function


class BeneficiaryExport(ExportableMixin, IcdsSqlData):
    title = 'Child Beneficiary'
    table_name = 'child_health_monthly_view'

    def __init__(self, config=None, loc_level=1, show_test=False, beta=False):
        config.update({
            '5_years': 60,
        })
        self.config = config
        self.loc_level = loc_level
        self.show_test = show_test
        self.beta = beta

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
            'unweighed': RawFilter('recorded_weight IS NULL'),
            'umeasured': RawFilter('recorded_height IS NULL'),
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
            return self._map_filter_name_to_sql_filter(filters[0])
        return ORFilter([
            self._map_filter_name_to_sql_filter(filter_name)
            for filter_name in filters
        ])

    @property
    def filters(self):
        filters = [LTE('age_in_months', '5_years')]
        for key, value in six.iteritems(self.config):
            if key == 'domain' or key == '5_years':
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

        def test_fucntion(x):
            return format_decimal(x) if x else DATA_NOT_ENTERED

        columns = [
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
                'Supervisor Name',
                SimpleColumn('supervisor_name'),
                slug='supervisor_name'
            ),
            DatabaseColumn(
                'Block Name',
                SimpleColumn('block_name'),
                slug='block_name'
            ),
            DatabaseColumn(
                'AWW Phone Number',
                SimpleColumn('aww_phone_number'),
                format_fn=phone_number_function,
                slug='aww_phone_number'
            ),
            DatabaseColumn(
                'Mother Phone Number',
                SimpleColumn('mother_phone_number'),
                format_fn=phone_number_function,
                slug='mother_phone_number'
            ),
            DatabaseColumn(
                'Child Name',
                SimpleColumn('person_name'),
                slug='person_name'
            ),
            DatabaseColumn(
                'Date of Birth',
                SimpleColumn('dob'),
                slug='dob'
            ),
            DatabaseColumn(
                'Current Age (as of {})'.format(selected_month.isoformat()),
                AliasColumn('dob'),
                format_fn=lambda x: calculate_date_for_age(x, self.config['month']),
                slug='current_age'
            ),
            DatabaseColumn(
                'Sex ',
                SimpleColumn('sex'),
                slug='sex'
            ),
            ICDSDatabaseColumn(
                '1 Year Immunizations Complete',
                SimpleColumn('fully_immunized'),
                format_fn=lambda x: 'Yes' if x else 'No'
            ),
            DatabaseColumn(
                'Month for data shown',
                SimpleColumn('month'),
                slug='month'
            ),
            DatabaseColumn(
                'Weight Recorded (in Month)',
                SimpleColumn('recorded_weight'),
                format_fn=test_fucntion,
                slug='recorded_weight'
            ),
            DatabaseColumn(
                'Height Recorded (in Month)',
                SimpleColumn('recorded_height'),
                format_fn=test_fucntion,
                slug='recorded_height'
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
                slug="current_month_wasting_v2"
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
                slug="current_month_stunting_v2"
            ),
            DatabaseColumn(
                'Days attended PSE (as of {})'.format(selected_month.isoformat()),
                SimpleColumn('pse_days_attended'),
                slug="pse_days_attended"
            ),
        ]
        return columns

    @property
    def columns(self):
        return self.get_columns_by_loc_level

from __future__ import absolute_import
from __future__ import unicode_literals
from io import BytesIO
import datetime

import pytz
from sqlagg.filters import EQ, IN, NOT
from sqlagg.sorting import OrderBy

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.sqlreport import Column

from corehq.apps.reports.util import get_INFilter_bindparams
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from custom.utils.utils import clean_IN_filter_value
import six

FILTER_BY_LIST = {
    'unweighed': 'Data not Entered for weight (Unweighed)',
    'umeasured': 'Data not Entered for height (Unmeasured)',
    'severely_underweight': 'Severely Underweight',
    'moderately_underweight': 'Moderately Underweight',
    'normal_wfa': 'Normal (weight-for-age)',
    'severely_stunted': 'Severely Stunted',
    'moderately_stunted': 'Moderately Stunted',
    'normal_hfa': 'Normal (height-for-age)',
    'severely_wasted': 'Severely Wasted',
    'moderately_wasted': 'Moderately Wasted',
    'normal_wfh': 'Normal (weight-for-height)'
}


class ExportableMixin(object):
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level=1, show_test=False, beta=False):
        self.config = config
        self.loc_level = loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test
        self.beta = beta

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = []
        infilter_params = get_INFilter_bindparams('excluded_states', self.excluded_states)

        if not self.show_test:
            filters.append(NOT(IN('state_id', infilter_params)))

        for key, value in six.iteritems(self.config):
            if key == 'domain' or key in infilter_params or 'age' in key:
                continue
            filters.append(EQ(key, key))
        return filters

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = ['aggregation_level']
        for column in group_by_columns:
            group_by.append(column.slug)
        return group_by

    @property
    def order_by(self):
        order_by_columns = self.get_columns_by_loc_level
        order_by = []
        for column in order_by_columns:
            order_by.append(OrderBy(column.slug))
        return order_by

    def to_export(self, format, location):
        export_file = BytesIO()
        excel_data = self.get_excel_data(location)

        export_from_tables(excel_data, export_file, format)
        return export_response(export_file, format, self.title)

    def get_excel_data(self, location):
        excel_rows = []
        headers = []
        for column in self.columns:
            if isinstance(column, Column):
                headers.append(column.header)
            else:
                headers.append(column['header'])
        excel_rows.append(headers)
        for row in self.get_data():
            row_data = []
            for c in self.columns:
                if isinstance(c, Column):
                    cell = row[c.slug]
                else:
                    cell = row[c['slug']]
                if not isinstance(cell, dict):
                    row_data.append(cell if cell else DATA_NOT_ENTERED)
                else:
                    row_data.append(cell['sort_key'] if cell and 'sort_key' in cell else cell)
            excel_rows.append(row_data)
        filters = [['Generated at', india_now()]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        if 'aggregation_level' in self.config:
            levels = ['State', 'District', 'Block', 'Supervisor', 'AWC']
            filters.append(['Grouped By', levels[self.config['aggregation_level'] - 1]])
        if 'month' in self.config:
            date = self.config['month']
            filters.append(['Month', date.strftime("%B")])
            filters.append(['Year', date.year])
        if 'filters' in self.config:
            filter_values = []
            for filter_by in self.config['filters']:
                filter_values.append(FILTER_BY_LIST[filter_by])
            filters.append(['Filtered By', ', '.join(filter_values)])
        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                filters
            ]
        ]


class ProgressReportMixIn(object):

    @property
    def filters(self):
        filters = [
            EQ('aggregation_level', 'aggregation_level')
        ]
        keys = ['state_id', 'district_id', 'block_id', 'supervisor_id']
        for key in keys:
            if key in self.config:
                filters.append(
                    EQ(key, key)
                )
        return filters

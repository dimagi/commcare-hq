from __future__ import absolute_import

from __future__ import unicode_literals
from sqlagg.filters import EQ, IN, NOT

from corehq.apps.reports.util import get_INFilter_bindparams
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.utils.utils import clean_IN_filter_value


class NationalAggregationDataSource(IcdsSqlData):

    def __init__(self, config, data_source=None, show_test=False, beta=False):
        super(NationalAggregationDataSource, self).__init__(config)
        excluded_states = get_test_state_locations_id(self.config['domain'])
        self.config.update({
            'aggregation_level': 1,
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72',
            'excluded_states': excluded_states
        })
        clean_IN_filter_value(self.config, 'excluded_states')
        self.data_source = data_source
        self.excluded_states = excluded_states
        self.beta = beta
        self.show_test = show_test

    @property
    def table_name(self):
        return self.data_source.table_name

    @property
    def engine_id(self):
        return self.data_source.engine_id

    @property
    def filters(self):
        filters = [
            EQ('aggregation_level', 'aggregation_level'),
            EQ('month', 'previous_month')
        ]
        if not self.show_test:
            filters.append(NOT(IN('state_id', get_INFilter_bindparams('excluded_states', self.excluded_states))))
        return filters

    @property
    def group_by(self):
        return ['month']

    @property
    def columns(self):
        # drop month column because we always fetch data here for previous month
        return self.data_source.get_columns(self.filters)

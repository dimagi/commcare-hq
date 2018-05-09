from __future__ import absolute_import

from sqlagg.filters import EQ, IN, NOT

from corehq.apps.reports.sqlreport import SqlData
from corehq.apps.reports.util import get_INFilter_bindparams


class NationalAggregationDataSource(SqlData):

    def __init__(self, config, excluded_states, data_source=None, show_test=False, beta=False):
        super(NationalAggregationDataSource, self).__init__(config)
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
        return []

    @property
    def columns(self):
        # drop month column because we always fetch data here for previous month
        return self.data_source.columns[1:]
